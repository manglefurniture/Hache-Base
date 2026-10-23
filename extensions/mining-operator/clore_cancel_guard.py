#!/usr/bin/env python3
"""Independent, fail-persistent cancellation watchdog for Clore orders.

Read-only until an operator with root privileges arms one already-authorized order.
NO RENTAL/BIDDING CODE. An order MUST be armed before any future rental flow is enabled.
"""
import argparse
from decimal import Decimal, InvalidOperation, ROUND_FLOOR
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_DB = "/var/lib/hache-mining-operator/clore-cancel.sqlite3"
API = "https://api.clore.ai/v1/"
# Reserve 15% for estimated fees, billing lag, API delay and rounding. Not a hard cap.
SAFETY_RATIO = Decimal("0.85")
# Up to 5% estimated provider fees on top of the approved daily bid.
FEE_FACTOR = Decimal("1.05")
# Timer jitter (30 s) + API delay/retry buffer; no late enrollment.
MIN_REMAINING_SECONDS = 90
SCHEMA = """
CREATE TABLE IF NOT EXISTS clore_cancel_leases (
 order_id INTEGER PRIMARY KEY CHECK(order_id > 0),
 server_id INTEGER NOT NULL CHECK(server_id > 0),
 daily_bid_usd TEXT NOT NULL,
 budget_usd TEXT NOT NULL,
 creation_fee_usd TEXT NOT NULL,
 max_minutes INTEGER NOT NULL,
 created_at INTEGER NOT NULL,
 cutoff_at INTEGER NOT NULL,
 phase TEXT NOT NULL CHECK(phase IN ('armed','closed')),
 last_attempt INTEGER,
 last_outcome TEXT NOT NULL DEFAULT 'armed',
 confirmed_at INTEGER
);
CREATE INDEX IF NOT EXISTS clore_cancel_pending
 ON clore_cancel_leases(phase, cutoff_at);
CREATE TABLE IF NOT EXISTS clore_cancel_heartbeat (
 id INTEGER PRIMARY KEY CHECK(id=1),
 completed_at INTEGER NOT NULL
);
"""

class GuardError(Exception):
    pass

def decimal_amount(value, name):
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise GuardError("invalid_" + name) from None
    if not d.is_finite() or not Decimal("0") < d <= Decimal("1000"):
        raise GuardError("invalid_" + name)
    return d

def db_open(path):
    connection = sqlite3.connect(str(path), isolation_level=None, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout=5000")
    connection.executescript(SCHEMA)
    return connection

def verify_billing_order(order, *, order_id, server_id, daily_bid_usd, creation_fee_usd, created_at):
    """Fail closed unless a fresh authenticated provider order is in USD.

    Clore represents the unified USDT/USDC deposit and rental balance as
    'USD-Blockchain' in the API, NOT 'usd' or the deposit token name.
    Never mix CLORE/bitcoin-denominated values into the USD budget.
    """
    if type(order) is not dict or order.get("id") != order_id:
        raise GuardError("provider_order_not_verified")
    if order.get("currency") != "USD-Blockchain":
        raise GuardError("usd_blockchain_billing_not_verified")
    if order.get("spot") is not True or order.get("expired") is not False:
        raise GuardError("not_a_live_spot_order")
    if type(order.get("si")) is not int or order["si"] != server_id:
        raise GuardError("provider_server_mismatch")
    if type(order.get("ct")) is not int or order["ct"] != created_at:
        raise GuardError("provider_creation_time_mismatch")
    try:
        price = Decimal(str(order.get("price")))
        fee = Decimal(str(order.get("fee")))
        creation = Decimal(str(order.get("creation_fee")))
        spent = Decimal(str(order.get("spend")))
        bid = decimal_amount(daily_bid_usd, "daily_bid")
        expected_creation = Decimal(str(creation_fee_usd))
    except (InvalidOperation, ValueError, TypeError):
        raise GuardError("invalid_provider_order_money") from None
    if (not all(x.is_finite() for x in (price, fee, creation, spent, expected_creation)) or
            not 0 < price <= bid or not 0 <= fee <= 5 or
            not 0 <= spent or not 0 <= creation or creation != expected_creation):
        raise GuardError("provider_order_price_or_fee_unverified")
    return True


def arm(db, *, order_id, server_id, daily_bid_usd, budget_usd,
        creation_fee_usd, max_minutes, created_at, provider_order=None,
        now=None, timer_check=None):
    """Register only a *known order ID*, never issue a rental or a bid."""
    now = int(time.time()) if now is None else int(now)
    if timer_check is None:
        def timer_check():
            try:
                return subprocess.run(
                    ["systemctl", "is-active", "--quiet",
                     "hache-mining-operator-clore-cancel.timer"],
                    timeout=3, capture_output=True).returncode == 0
            except (OSError, subprocess.TimeoutExpired):
                return False
    if not timer_check():
        raise GuardError("independent_cancel_timer_inactive")
    hb = db.execute("SELECT completed_at FROM clore_cancel_heartbeat WHERE id=1").fetchone()
    if not hb or not 0 <= now - hb[0] <= 90:
        raise GuardError("independent_cancel_supervisor_unhealthy")
    if type(order_id) is not int or type(server_id) is not int or not 0 < order_id < 10**15 or not 0 < server_id < 10**15:
        raise GuardError("invalid_order_identity")
    if type(max_minutes) is not int or not 1 <= max_minutes <= 1440:
        raise GuardError("invalid_minutes")
    if type(created_at) is not int or not now - 172800 <= created_at <= now:
        raise GuardError("unverified_creation_time")
    bid = decimal_amount(daily_bid_usd, "daily_bid")
    budget = decimal_amount(budget_usd, "budget")
    try:
        creation_fee = Decimal(str(creation_fee_usd))
    except (InvalidOperation, ValueError, TypeError):
        raise GuardError("invalid_creation_fee") from None
    if not creation_fee.is_finite() or not 0 <= creation_fee <= Decimal("1000"):
        raise GuardError("invalid_creation_fee")
    verify_billing_order(provider_order, order_id=order_id, server_id=server_id,
                         daily_bid_usd=daily_bid_usd, creation_fee_usd=creation_fee_usd,
                         created_at=created_at)
    remaining = budget - creation_fee
    if remaining <= 0:
        raise GuardError("creation_fee_exceeds_budget")
    # The provider's actual fixed creation fee must not be spent twice.
    affordable_seconds = int((remaining * SAFETY_RATIO * 86400 / (bid * FEE_FACTOR)).to_integral_value(rounding=ROUND_FLOOR))
    cutoff = created_at + min(max_minutes * 60, affordable_seconds)
    if cutoff - now < MIN_REMAINING_SECONDS:
        raise GuardError("insufficient_time_for_independent_cancel_cycle")
    db.execute("BEGIN IMMEDIATE")
    try:
        if db.execute("SELECT 1 FROM clore_cancel_leases WHERE phase='armed' LIMIT 1").fetchone():
            raise GuardError("existing_armed_order")
        db.execute(
            "INSERT INTO clore_cancel_leases "
            "(order_id,server_id,daily_bid_usd,budget_usd,creation_fee_usd,max_minutes,created_at,cutoff_at,phase) "
            "VALUES(?,?,?,?,?,?,?,?,'armed')",
            (order_id, server_id, str(bid), str(budget), str(creation_fee),
             max_minutes, created_at, cutoff))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"order_id": order_id, "server_id": server_id, "cutoff_at": cutoff, "state": "armed"}

class CloreAPI:
    """Fixed HTTPS endpoints only; token never enters logs or subprocess argv."""
    def __init__(self, token, *, transport=None):
        if not token or any(c.isspace() for c in token):
            raise GuardError("clore_credential_unavailable")
        self._token = token
        self.transport = transport or urlopen

    def _request(self, endpoint, body=None):
        if endpoint not in ("my_orders?return_completed=true", "cancel_order"):
            raise GuardError("unsupported_endpoint")
        headers = {"auth": self._token, "Accept": "application/json"}
        method = "GET"
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            method = "POST"
            data = json.dumps(body, separators=(",", ":")).encode()
        request = Request(API + endpoint, headers=headers, data=data, method=method)
        try:
            with self.transport(request, timeout=12) as response:
                raw = response.read(524289)
        except (HTTPError, URLError, OSError, TimeoutError):
            raise GuardError("provider_request_failed") from None
        if len(raw) > 524288:
            raise GuardError("oversize_provider_response")
        try:
            result = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            raise GuardError("invalid_provider_response") from None
        if not isinstance(result, dict) or result.get("code") != 0:
            raise GuardError("provider_rejected")
        return result

    def inventory(self):
        """Authenticated complete-format inventory metadata for pre-rent risk checks.

        The API's limit is an active-order cap, not proof of history pagination.
        Read-only and unchanged authorization/credential path.
        """
        result = self._request("my_orders?return_completed=true")
        limit = result.get("limit")
        if type(limit) is not int or not 1 <= limit <= 10000:
            raise GuardError("unverifiable_inventory_limit")
        rows = result.get("orders")
        if type(rows) is not list or len(rows) > 10000:
            raise GuardError("invalid_orders_list")
        ids = set()
        for row in rows:
            if (type(row) is not dict or type(row.get("id")) is not int or
                    not 0 < row["id"] < 10**15 or row["id"] in ids):
                raise GuardError("invalid_orders_list")
            ids.add(row["id"])
        return {"limit": limit, "orders": rows}

    def orders(self):
        result = self._request("my_orders?return_completed=true")
        orders = result.get("orders")
        if not isinstance(orders, list) or len(orders) > 10000:
            raise GuardError("invalid_orders_list")
        ids = set()
        for order in orders:
            if not isinstance(order, dict) or type(order.get("id")) is not int or order["id"] <= 0 or order["id"] in ids:
                raise GuardError("invalid_orders_list")
            ids.add(order["id"])
        return orders

    def cancel(self, order_id):
        self._request("cancel_order", {"id": order_id})

def heartbeat(db, now):
    db.execute("INSERT INTO clore_cancel_heartbeat(id,completed_at) VALUES(1,?) "
               "ON CONFLICT(id) DO UPDATE SET completed_at=excluded.completed_at", (now,))

def record(db, order_id, now, outcome, *, closed=False, attempted=False):
    db.execute(
        "UPDATE clore_cancel_leases SET last_outcome=?, "
        "last_attempt=CASE WHEN ? THEN ? ELSE last_attempt END, "
        "phase=CASE WHEN ? THEN 'closed' ELSE phase END, "
        "confirmed_at=CASE WHEN ? THEN ? ELSE confirmed_at END WHERE order_id=?",
        (outcome, int(attempted), now, int(closed), int(closed), now, order_id))

def tick(db, api, *, now=None, delay=lambda seconds: time.sleep(seconds)):
    """A successful POST never closes a lease; only provider confirmed expired does."""
    now = int(time.time()) if now is None else int(now)
    leases = db.execute("SELECT * FROM clore_cancel_leases WHERE phase='armed' ORDER BY cutoff_at").fetchall()
    if not leases:
        # The heartbeat must prove actual API authentication even while idle.
        api.orders()
        heartbeat(db, now)
        return {"active": 0, "status": "idle"}
    if len(leases) > 1:
        raise GuardError("multiple_armed_orders")
    row = leases[0]
    oid = row["order_id"]
    due = now >= row["cutoff_at"]
    try:
        orders = api.orders()
        heartbeat(db, now)
        match = next((x for x in orders if x["id"] == oid), None)
        if match is None:
            record(db, oid, now, "provider_order_not_in_history")
            if not due:
                return {"active": 1, "status": "order_not_found"}
        else:
            # Do not cancel an unexpected server when a provider supplies identity.
            server = match.get("si", match.get("server_id"))
            if server is not None and (type(server) is not int or server != row["server_id"]):
                record(db, oid, now, "order_server_identity_mismatch")
                raise GuardError("order_server_identity_mismatch")
            if match.get("expired") is True:
                record(db, oid, now, "provider_confirmed_expired", closed=True)
                return {"active": 0, "status": "verified_closed"}
            if match.get("expired") is False:
                # All monetary fields MUST be in USD; native BTC/CLORE prices
                # cannot be compared numerically with a USD spending cap.
                if match.get("currency") != "USD-Blockchain" or match.get("spot") is not True:
                    due = True
                    record(db, oid, now, "currency_or_spot_identity_mismatch")
                try:
                    actual = Decimal(str(match.get("price")))
                    fees = Decimal(str(match.get("fee")))
                    spent = Decimal(str(match.get("spend")))
                    created = Decimal(str(match.get("creation_fee")))
                    if (not all(x.is_finite() for x in (actual, fees, spent, created)) or
                            actual <= 0 or actual > Decimal(row["daily_bid_usd"]) or
                            fees < 0 or fees > 5 or spent < 0 or created < 0 or
                            created != Decimal(row["creation_fee_usd"]) or
                            spent + created >= Decimal(row["budget_usd"]) * SAFETY_RATIO):
                        due = True
                except (InvalidOperation, ValueError, TypeError):
                    due = True
                try:
                    oc = Decimal(str(match.get("oc_price", 0)))
                    if not oc.is_finite() or oc != 0:
                        due = True
                except (InvalidOperation, ValueError, TypeError):
                    due = True
            if match.get("expired") is not False:
                record(db, oid, now, "unknown_order_state")
                if not due:
                    raise GuardError("unknown_order_state")
            if not due:
                record(db, oid, now, "watching")
                return {"active": 1, "status": "watching", "cutoff_at": row["cutoff_at"]}
    except GuardError as exc:
        # Provider reads may fail at precisely the deadline. Still attempt a stop;
        # except when the provider explicitly identifies the wrong server.
        if str(exc) in ("order_server_identity_mismatch", "unknown_order_state") and not due:
            raise
        if str(exc) == "order_server_identity_mismatch":
            raise
        if not due:
            record(db, oid, now, str(exc))
            raise
    # No live spend when now < cutoff. A direct POST is allowed only after deadline.
    if not due:
        return {"active": 1, "status": "watching"}
    try:
        delay(1.1)  # account-wide Clore rate limit, including initial GET
        api.cancel(oid)
        record(db, oid, now, "cancel_submitted_unverified", attempted=True)
        return {"active": 1, "status": "cancel_submitted_unverified"}
    except GuardError:
        record(db, oid, now, "cancel_failed_retry_next_tick", attempted=True)
        raise GuardError("cancel_failed_retry_next_tick") from None

def credential():
    directory = os.environ.get("CREDENTIALS_DIRECTORY")
    if not directory:
        raise GuardError("systemd_credential_required")
    path = Path(directory) / "clore_key"
    if path.is_symlink() or not path.is_file():
        raise GuardError("clore_credential_unavailable")
    token = path.read_text().strip()
    if len(token) < 16:
        raise GuardError("clore_credential_unavailable")
    return token

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=DEFAULT_DB)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("tick")
    sub.add_parser("status")
    ar = sub.add_parser("arm")
    ar.add_argument("--approved", action="store_true", help="Owner has approved exact spending and order")
    ar.add_argument("--order-id", type=int, required=True)
    ar.add_argument("--server-id", type=int, required=True)
    ar.add_argument("--daily-bid-usd", required=True)
    ar.add_argument("--budget-usd", required=True)
    ar.add_argument("--creation-fee-usd", required=True)
    ar.add_argument("--max-minutes", type=int, required=True)
    ar.add_argument("--created-unix", type=int, required=True)
    args = parser.parse_args()
    try:
        if args.action == "arm" and (os.geteuid() != 0 or not args.approved):
            raise GuardError("root_and_exact_owner_approval_required")
        db = db_open(args.db)
        try:
            if args.action == "arm":
                # Authenticated provider identity/currency is a required
                # enrollment gate, never trust a manually asserted USD quote.
                provider_orders = CloreAPI(credential()).orders()
                matches = [o for o in provider_orders if o["id"] == args.order_id]
                if len(matches) != 1:
                    raise GuardError("provider_order_not_verified")
                output = arm(db, order_id=args.order_id, server_id=args.server_id,
                             provider_order=matches[0],
                             daily_bid_usd=args.daily_bid_usd, budget_usd=args.budget_usd,
                             creation_fee_usd=args.creation_fee_usd,
                             max_minutes=args.max_minutes, created_at=args.created_unix)
            elif args.action == "tick":
                output = tick(db, CloreAPI(credential()))
            else:
                output = {"leases": [dict(row) for row in db.execute(
                    "SELECT order_id,server_id,cutoff_at,phase,last_attempt,last_outcome,confirmed_at "
                    "FROM clore_cancel_leases ORDER BY cutoff_at DESC LIMIT 10")]}
        finally:
            db.close()
        print(json.dumps(output, sort_keys=True))
    except (GuardError, OSError, sqlite3.Error) as exc:
        # Never print provider response bodies, auth, credentials or unsanitized exceptions.
        msg = str(exc) if isinstance(exc, GuardError) else "local_state_unavailable"
        print(json.dumps({"ok": False, "error": msg}), file=sys.stderr)
        return 2
    return 0

if __name__ == "__main__":
    sys.exit(main())
