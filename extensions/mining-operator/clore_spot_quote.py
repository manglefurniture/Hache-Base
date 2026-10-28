#!/usr/bin/env python3
"""Clore per-server Spot competition quote. READ ONLY, no bids or grants.

Runs only under the hache-miner identity with a systemd private clore_key
credential. Never call this with the API key on a command line or via Telegram.
Quote output is sanitized, time bounded, and NOT an executable bid price.
"""
import argparse
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_UP
from http.client import HTTPException
import json
import os
from pathlib import Path
import re
import ssl
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPSHandler, HTTPRedirectHandler

BASE = "https://api.clore.ai/v1/spot_marketplace?market="
MAX_BYTES = 262144
MAX_OFFERS = 1000
USD = "USD-Blockchain"
CURRENCIES = (USD, "bitcoin", "CLORE-Blockchain")

class SpotError(ValueError):
    pass

def number(value, *, zero=False):
    if type(value) not in (str, float, int) or isinstance(value, bool):
        raise SpotError("invalid_spot_price")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise SpotError("invalid_spot_price") from None
    if (not amount.is_finite() or amount > Decimal("100000000") or
            (amount < 0 if zero else amount <= 0)):
        raise SpotError("invalid_spot_price")
    return amount

def currency_rate(rates, currency):
    if currency == USD:
        rate = rates.get(currency, 1)
        converted = number(rate)
        if converted != 1:
            raise SpotError("unexpected_usd_exchange_rate")
        return converted
    if type(rates) is not dict or currency not in rates:
        raise SpotError("missing_competing_currency_rate")
    return number(rates[currency])

def validate_id(server_id):
    if type(server_id) is not int or not 0 < server_id < 10**15:
        raise SpotError("invalid_server_id")
    return server_id

def parse_spot(snapshot, server_id, *, now=None):
    """Sanitize the authenticated provider snapshot; no raw response escapes."""
    validate_id(server_id)
    if (type(snapshot) is not dict or snapshot.get("code") != 0
            or snapshot.get("exists") is not True
            or type(snapshot.get("market")) is not dict):
        raise SpotError("spot_market_not_available")
    market = snapshot["market"]
    server = market.get("server")
    offers = market.get("offers")
    rates = market.get("currency_rates_in_usd")
    if (type(server) is not dict or type(offers) is not list
            or len(offers) > MAX_OFFERS or type(rates) is not dict):
        raise SpotError("spot_market_incomplete")
    if server.get("online") is not True or server.get("visibility") != "public":
        raise SpotError("spot_server_not_public_online")
    min_pricing = server.get("min_pricing")
    if type(min_pricing) is not dict or USD not in min_pricing:
        raise SpotError("spot_usd_not_supported")
    floor = number(min_pricing[USD])
    mrl = server.get("mrl")
    if type(mrl) not in (int, float) or not 0 < mrl <= 8760:
        raise SpotError("spot_mrl_unverified")

    top = Decimal("0")
    incumbent = 0
    own = 0
    for item in offers:
        if type(item) is not dict or set(("offer_id","bid","currency","active","my")) - set(item):
            raise SpotError("spot_competition_incomplete")
        if (type(item["offer_id"]) is not int or not 0 < item["offer_id"] < 10**15 or
                type(item["active"]) is not bool or type(item["my"]) is not bool):
            raise SpotError("spot_competition_incomplete")
        currency = item["currency"]
        if currency not in CURRENCIES:
            raise SpotError("unknown_spot_currency")
        usd = number(item["bid"]) * currency_rate(rates, currency)
        top = max(top, usd)
        if item["active"]:
            incumbent += 1
        if item["my"]:
            own += 1
    # 1% is only an illustration of a possible next competitive bid.
    # The provider enforces its live, currency-specific minimum step and cap.
    illustrative = max(floor, top * Decimal("1.01"))
    rate = Decimal("0.0001")
    observed = now or datetime.now(timezone.utc)
    if observed.tzinfo is None:
        raise SpotError("invalid_observation_timestamp")
    fmt = lambda v: float(v.quantize(rate, rounding=ROUND_UP))
    return {
        "server_id": server_id,
        "source": "clore_spot_marketplace_authenticated_readonly",
        "observed_at": observed.astimezone(timezone.utc).isoformat(timespec="seconds"),
        "currency": USD,
        "minimum_usd_day": fmt(floor),
        "highest_bid_usd_day": fmt(top),
        "illustrative_1pct_usd_day": fmt(illustrative),
        "illustrative_1pct_usd_hour": fmt(illustrative / 24),
        "bid_count": len(offers),
        "active_bids": incumbent,
        "own_bids": own,
        "server_mrl_hours": float(mrl),
        "online": True,
        "public": True,
        "rental_permitted": False,
        "executable_quote": False,
        "net_profit_verified": False,
        "warning": ("READ ONLY: illustrative price, NOT a valid or winning bid. "
                    "Clore enforces live min_price, minimum raise, maximum and fees. "
                    "No order is created, no spending is authorized.")
    }

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None

def fetch_spot(server_id, key, *, transport=None, now=None):
    """One HTTPS GET to a fixed endpoint, authenticated from a private credential."""
    validate_id(server_id)
    if type(key) is not str or not 20 <= len(key) <= 200 or any(c.isspace() for c in key):
        raise SpotError("credential_unavailable")
    endpoint = BASE + str(server_id)
    opener = build_opener(HTTPSHandler(context=ssl.create_default_context()), NoRedirect())
    transport = transport or opener.open
    request = Request(endpoint, method="GET",
                      headers={"auth": key, "Accept": "application/json",
                               "User-Agent": "Hache-Spot-Quote-ReadOnly/1"})
    try:
        with transport(request, timeout=12) as response:
            if getattr(response, "status", 200) != 200:
                raise SpotError("spot_unavailable")
            raw = response.read(MAX_BYTES + 1)
    except (HTTPError, URLError, OSError, TimeoutError, HTTPException):
        raise SpotError("spot_unavailable") from None
    if len(raw) > MAX_BYTES:
        raise SpotError("spot_response_too_large")
    try:
        data = json.loads(raw)
    except (UnicodeError, ValueError):
        raise SpotError("spot_bad_response") from None
    return parse_spot(data, server_id, now=now)

def credential():
    """Restricted to a systemd LoadCredential directory, never Telegram."""
    directory = os.environ.get("CREDENTIALS_DIRECTORY")
    if not directory:
        raise SpotError("systemd_credential_required")
    path = Path(directory) / "clore_key"
    try:
        # systemd credentials directory is private to the service, not a user path.
        return path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        raise SpotError("credential_unavailable") from None

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server-id", required=True, type=int)
    args = parser.parse_args(argv)
    try:
        result = fetch_spot(args.server_id, credential())
    except SpotError as exc:
        # No secrets, URLs with tokens, full server payloads or credential paths.
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps({"ok": True, "result": result}, sort_keys=True))
    return 0

if __name__ == "__main__":
    sys.exit(main())
