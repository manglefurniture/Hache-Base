#!/usr/bin/env python3
"""Independent Kryptex worker proof for *already registered* Clore financial leases.

The pool reports the last accepted share independently of a rented container.
Only an administrator may opt an exact armed order into this monitor. No rental,
bidding, arbitrary command execution, or provider cancellation occurs here.
"""
import json
from http.client import HTTPException
import re
import sqlite3
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

POOL = "https://pool.kryptex.com/prl/api/v3/miner/workers/"
SILENCE_SECONDS = 300
# Clore instances may need initial setup, but that grace starts when billed.
STARTUP_SECONDS = 300
WALLET_PATTERN = re.compile(r"prl1[023456789acdefghjklmnpqrstuvwxyz]{25,115}\Z")
SCHEMA = """
CREATE TABLE IF NOT EXISTS clore_pool_monitors (
 order_id INTEGER PRIMARY KEY,
 server_id INTEGER NOT NULL,
 wallet TEXT NOT NULL,
 worker TEXT NOT NULL,
 enrolled_at INTEGER NOT NULL,
 last_share_at INTEGER,
 last_checked_at INTEGER,
 last_outcome TEXT NOT NULL DEFAULT 'enrolled',
 FOREIGN KEY(order_id) REFERENCES clore_cancel_leases(order_id)
);
"""

class PoolError(Exception):
    pass

def valid_wallet(wallet):
    if type(wallet) is not str or not WALLET_PATTERN.fullmatch(wallet):
        raise PoolError("invalid_pool_wallet")
    return wallet

def enroll(db, *, order_id, wallet, now=None):
    """Explicit, one-time enrollment; no implicit monitoring of historic leases."""
    now = int(time.time()) if now is None else int(now)
    valid_wallet(wallet)
    if type(order_id) is not int or not 0 < order_id < 10**15:
        raise PoolError("invalid_pool_order")
    row = db.execute("SELECT order_id,server_id,phase,created_at,cutoff_at "
                     "FROM clore_cancel_leases WHERE order_id=?", (order_id,)).fetchone()
    if row is None or row["phase"] != "armed":
        raise PoolError("order_not_financially_armed")
    if not row["created_at"] <= now < row["cutoff_at"]:
        raise PoolError("order_outside_monitor_window")
    if now >= row["created_at"] + STARTUP_SECONDS:
        raise PoolError("monitor_enrollment_too_late")
    # Worker identity must exactly match the Clore container's order-bound worker.
    worker = "CLORE-" + str(order_id)
    try:
        db.execute("INSERT INTO clore_pool_monitors "
                   "(order_id,server_id,wallet,worker,enrolled_at) VALUES(?,?,?,?,?)",
                   (order_id, row["server_id"], wallet, worker, now))
    except sqlite3.IntegrityError:
        raise PoolError("monitor_already_enrolled") from None
    return {"order_id": order_id, "worker": worker, "monitoring": True}

class KryptexAPI:
    """Fixed HTTPS read-only API. No wallet is written to logs."""
    def __init__(self, *, transport=None):
        self.transport = transport or urlopen

    def last_share(self, wallet, worker):
        valid_wallet(wallet)
        if not re.fullmatch(r"CLORE-[1-9][0-9]{0,14}", worker):
            raise PoolError("invalid_pool_worker")
        req = Request(POOL + wallet, headers={"Accept": "application/json"},
                      method="GET")
        try:
            with self.transport(req, timeout=8) as response:
                if getattr(response, "status", 200) != 200:
                    raise PoolError("pool_unavailable")
                payload = response.read(262145)
        except (HTTPError, URLError, OSError, TimeoutError, HTTPException):
            raise PoolError("pool_unavailable") from None
        if len(payload) > 262144:
            raise PoolError("pool_oversize")
        try:
            data = json.loads(payload)
        except (ValueError, UnicodeDecodeError):
            raise PoolError("pool_invalid_json") from None
        if type(data) is not dict or type(data.get("results")) is not list:
            raise PoolError("pool_invalid_workers")
        workers = data["results"]
        if len(workers) > 5000:
            raise PoolError("pool_inventory_unbounded")
        # Reject possible pagination: missing workers cannot be interpreted as idle.
        count = data.get("count")
        if count is not None and (type(count) is not int or count != len(workers)):
            raise PoolError("pool_inventory_incomplete")
        matches = [x for x in workers if type(x) is dict and x.get("worker") == worker]
        if len(matches) > 1:
            raise PoolError("pool_duplicate_worker")
        if not matches:
            return None
        ts = matches[0].get("last_share")
        if type(ts) is not int or ts <= 0:
            raise PoolError("pool_share_time_invalid")
        return ts

def check(db, lease, *, now=None, pool=None):
    """Return a due reason only for explicitly monitored leases.

    The provider check remains mandatory even when the pool is unavailable.
    Pool errors never extend the last observed share, so a silent miner stops
    consuming paid rental time after a bounded interval.
    """
    now = int(time.time()) if now is None else int(now)
    oid = lease["order_id"]
    row = db.execute("SELECT * FROM clore_pool_monitors WHERE order_id=?", (oid,)).fetchone()
    if row is None:
        return None  # Legacy leases: unchanged deadline/budget-only behavior.
    if row["server_id"] != lease["server_id"] or row["worker"] != "CLORE-" + str(oid):
        return "pool_monitor_identity_mismatch"
    last_share = row["last_share_at"]
    outcome = "pool_unavailable"
    try:
        latest = (pool or KryptexAPI()).last_share(row["wallet"], row["worker"])
        outcome = "worker_missing" if latest is None else "worker_observed"
        if latest is not None:
            # Never accept shares before the order was created or in the future.
            if not lease["created_at"] <= latest <= now + 5:
                raise PoolError("pool_share_time_untrusted")
            last_share = max(latest, last_share or 0)
    except PoolError as exc:
        outcome = str(exc)
    db.execute("UPDATE clore_pool_monitors SET last_share_at=?,last_checked_at=?,"
               "last_outcome=? WHERE order_id=?", (last_share, now, outcome, oid))
    if now < lease["created_at"] + STARTUP_SECONDS and last_share is None:
        return None
    if last_share is None:
        return "worker_never_produced"
    if now - last_share >= SILENCE_SECONDS:
        return "worker_share_stale"
    return None
