#!/usr/bin/env python3
"""Durable Clore pre-order risk ledger. READ-ONLY against providers.

This module never issues create_order, cancel_order, shell, or root grants.
A reservation is NOT permission to rent. Designed to make a future
one-use approved executor recoverable across timeouts and restarts.
"""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re
import secrets
import sqlite3
import time

from clore_cancel_guard import GuardError, SAFETY_RATIO, FEE_FACTOR, decimal_amount

SCHEMA = """
CREATE TABLE IF NOT EXISTS clore_preorders(
 reservation_id TEXT PRIMARY KEY,
 terms_json TEXT NOT NULL,
 terms_sha256 TEXT NOT NULL,
 baseline_json TEXT NOT NULL,
 created_at INTEGER NOT NULL,
 expires_at INTEGER NOT NULL,
 phase TEXT NOT NULL CHECK(phase IN ('reserved','uncertain','reconciled','abandoned')),
 outcome TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS clore_preorders_single_active
 ON clore_preorders((1)) WHERE phase IN ('reserved','uncertain');
"""

FIELDS = frozenset({
    "server_id", "currency", "gpu_descriptor", "gpu_variant",
    "gpu_variant_verified", "image", "daily_bid_usd", "max_total_usd",
    "creation_fee_usd", "max_minutes", "quote_observed_at",
})
BLOCKING_PHASES = ("reserved", "uncertain")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def init_schema(db):
    db.executescript(SCHEMA)


def money(value, name, *, can_be_zero=False):
    if type(value) not in (str, int, float) or type(value) is bool:
        raise GuardError("invalid_" + name)
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise GuardError("invalid_" + name) from None
    if not amount.is_finite() or amount > 1000 or (amount < 0 if can_be_zero else amount <= 0):
        raise GuardError("invalid_" + name)
    return amount


def validate_terms(terms, now):
    """Require one precise and fresh physical server, GPU, image and USD budget."""
    if type(terms) is not dict or set(terms) != FIELDS:
        raise GuardError("invalid_preorder_contract")
    if type(terms["server_id"]) is not int or not 0 < terms["server_id"] < 10**15:
        raise GuardError("invalid_server_id")
    if terms["currency"] != "USD-Blockchain":
        raise GuardError("wrong_billing_currency")
    if terms["gpu_variant_verified"] is not True or terms["gpu_variant"] not in ("desktop", "laptop"):
        raise GuardError("gpu_variant_unverified")
    descriptor = terms["gpu_descriptor"]
    if type(descriptor) is not str or not 5 <= len(descriptor) <= 125 or not re.fullmatch(r"[A-Za-z0-9 ._()+/-]+", descriptor):
        raise GuardError("invalid_gpu_descriptor")
    image = terms["image"]
    if type(image) is not str or not re.fullmatch(r"[A-Za-z0-9./_:-]{15,240}@sha256:[a-f0-9]{64}", image):
        raise GuardError("image_must_be_pinned_by_digest")
    if type(terms["max_minutes"]) is not int or not 2 <= terms["max_minutes"] <= 1440:
        raise GuardError("invalid_max_minutes")
    stamp = terms["quote_observed_at"]
    if type(stamp) is not str or len(stamp) > 40:
        raise GuardError("invalid_quote_time")
    try:
        moment = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        if moment.tzinfo is None:
            raise ValueError("naive")
        age = now - int(moment.timestamp())
    except ValueError:
        raise GuardError("invalid_quote_time") from None
    if not 0 <= age <= 120:
        raise GuardError("stale_quote")
    daily = money(terms["daily_bid_usd"], "daily_bid")
    budget = money(terms["max_total_usd"], "total_budget")
    creation = money(terms["creation_fee_usd"], "creation_fee", can_be_zero=True)
    # An approved cap must comfortably cover the entire requested runtime;
    # expected fees and billing lag are not hard guarantees.
    minimum = creation + (daily * Decimal(terms["max_minutes"]) / Decimal(1440) * FEE_FACTOR)
    if budget * SAFETY_RATIO < minimum:
        raise GuardError("planned_exposure_exceeds_conservative_budget")
    return canonical(terms)


def inventory_baseline(api):
    """Require authenticated, whole inventory. No silent pagination/truncation."""
    data = api.inventory()  # Authenticated GET only, never creates an order.
    if type(data) is not dict or type(data.get("limit")) is not int or not 1 <= data["limit"] <= 10000:
        raise GuardError("unverifiable_inventory_limit")
    orders = data.get("orders")
    if type(orders) is not list or len(orders) > 10000:
        raise GuardError("invalid_inventory")
    ids, active = [], 0
    for order in orders:
        if type(order) is not dict or type(order.get("id")) is not int or not 0 < order["id"] < 10**15:
            raise GuardError("invalid_inventory")
        ids.append(order["id"])
        if order.get("expired") is not True:
            active += 1
    if len(set(ids)) != len(ids):
        raise GuardError("duplicate_order_identity")
    # Saturated inventory risks missing a parallel order or a provider-side
    # capacity ambiguity; refuse instead of pretending the baseline is full.
    if active >= data["limit"]:
        raise GuardError("inventory_capacity_or_completeness_uncertain")
    return sorted(ids)


def supervisor_healthy(db, now, timer_check):
    if timer_check is not True:
        raise GuardError("independent_cancel_timer_inactive")
    row = db.execute("SELECT completed_at FROM clore_cancel_heartbeat WHERE id=1").fetchone()
    if row is None or not 0 <= now - row[0] <= 90:
        raise GuardError("independent_cancel_supervisor_unhealthy")


def reserve(db, *, terms, api, now=None, timer_check=False):
    """Persist a one-use local risk hold BEFORE any future provider create.

    An authenticated approval/grant and the provider creation executor do
    not exist here. No write against provider is reachable from this code.
    """
    now = int(time.time()) if now is None else int(now)
    payload = validate_terms(terms, now)
    supervisor_healthy(db, now, timer_check)
    baseline = canonical(inventory_baseline(api))
    init_schema(db)
    reservation_id = secrets.token_hex(16)
    expires = now + 120
    db.execute("BEGIN IMMEDIATE")
    try:
        if db.execute("SELECT 1 FROM clore_cancel_leases WHERE phase='armed' LIMIT 1").fetchone():
            raise GuardError("active_clore_obligation")
        if db.execute("SELECT 1 FROM clore_preorders WHERE phase IN ('reserved','uncertain') LIMIT 1").fetchone():
            raise GuardError("existing_preorder_obligation")
        db.execute(
            "INSERT INTO clore_preorders "
            "(reservation_id,terms_json,terms_sha256,baseline_json,created_at,expires_at,phase,outcome) "
            "VALUES(?,?,?,?,?,?,'reserved','create_not_enabled')",
            (reservation_id, payload, hashlib.sha256(payload.encode()).hexdigest(),
             baseline, now, expires))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"reservation_id": reservation_id, "expires_at": expires,
            "baseline_count": len(json.loads(baseline)),
            "rental_permitted": False, "provider_mutation": False}


def evaluate_candidate(db, *, reservation_id, api, now=None):
    """Investigate a potential unknown create outcome; NEVER bind or cancel.

    An order is only *candidate* after exact identity, quote, pinned image
    and pricing checks; it still requires approved executor reconciliation.
    """
    now = int(time.time()) if now is None else int(now)
    if type(reservation_id) is not str or not re.fullmatch(r"[0-9a-f]{32}", reservation_id):
        raise GuardError("invalid_reservation_id")
    row = db.execute("SELECT terms_json,terms_sha256,baseline_json,created_at,expires_at,phase "
                     "FROM clore_preorders WHERE reservation_id=?", (reservation_id,)).fetchone()
    if row is None or row[5] not in BLOCKING_PHASES:
        raise GuardError("preorder_not_active")
    payload, expected_sha, baseline_json, created_at, expires_at, _phase = row
    if hashlib.sha256(payload.encode()).hexdigest() != expected_sha:
        raise GuardError("preorder_payload_tampered")
    terms = json.loads(payload)
    baseline = set(json.loads(baseline_json))
    inventory = api.inventory()
    ids = inventory_baseline_from_payload(inventory)
    if now < created_at or now - created_at > 86400:
        raise GuardError("preorder_reconciliation_out_of_range")
    added = [order for order in inventory["orders"] if order["id"] not in baseline]
    related = [o for o in added if o.get("si") == terms["server_id"]]
    if not related:
        return {"status": "not_found", "rental_permitted": False}
    if len(related) != 1:
        return {"status": "ambiguous", "rental_permitted": False}
    candidate = related[0]
    if (candidate.get("expired") is not False or candidate.get("spot") is not True or
            candidate.get("currency") != "USD-Blockchain" or
            candidate.get("image") != terms["image"] or
            type(candidate.get("ct")) is not int or
            not created_at - 2 <= candidate["ct"] <= expires_at + 120 or
            type(candidate.get("specs")) is not dict or
            candidate["specs"].get("gpu") != terms["gpu_descriptor"]):
        return {"status": "identity_mismatch", "rental_permitted": False}
    try:
        price = money(candidate.get("price"), "price")
        fee = money(candidate.get("fee"), "fee", can_be_zero=True)
        creation = money(candidate.get("creation_fee"), "creation_fee", can_be_zero=True)
        spend = money(candidate.get("spend"), "spend", can_be_zero=True)
        if (price > money(terms["daily_bid_usd"], "daily_bid") or fee > 5 or
                creation != money(terms["creation_fee_usd"], "creation_fee", can_be_zero=True) or
                spend + creation >= money(terms["max_total_usd"], "total") * SAFETY_RATIO):
            raise GuardError("spend_mismatch")
    except GuardError:
        return {"status": "price_or_fee_mismatch", "rental_permitted": False}
    return {"status": "candidate_unbound", "candidate_order_id": candidate["id"],
            "rental_permitted": False}


def inventory_baseline_from_payload(inventory):
    """Validate inventory structure without a second authenticated request."""
    class _Snapshot:
        def inventory(self):
            return inventory
    return inventory_baseline(_Snapshot())
