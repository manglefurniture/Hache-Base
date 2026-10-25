#!/usr/bin/env python3
"""Offline end-to-end Clore flow harness; NO live provider is accepted.

Intentionally not wired into the Telegram service or financial broker.
The caller has to possess separate Telegram and financial DB handles only
in an isolated test. Live deployment does NOT grant either user such access.
"""
from datetime import datetime, timezone
import hashlib
import hmac
import json
import re

from clore_cancel_guard import GuardError
from clore_create_journal import stage_once, record_unknown
from clore_preorder import reserve, evaluate_candidate, validate_terms


class SimulatedClore:
    """In-memory provider with no HTTP methods, credentials, or persistence."""
    def __init__(self, mode="success", limit=10):
        if mode not in ("success","timeout_after_create","timeout_before_create"):
            raise GuardError("invalid_simulation_mode")
        self.mode, self.limit = mode, limit
        self.orders, self.create_count = [], 0

    def inventory(self):
        return {"limit":self.limit,"orders":list(self.orders)}

    def simulated_create(self, terms, now):
        self.create_count += 1
        if self.create_count != 1:
            raise AssertionError("duplicate_simulated_create")
        if self.mode == "timeout_before_create":
            raise TimeoutError("synthetic_timeout")
        # Synthetic order only: cannot be interpreted as a Clore API receipt.
        order = {"id": 700001, "si": terms["server_id"], "spot": True,
                 "expired": False, "ct": now+1, "currency": "USD-Blockchain",
                 "image": terms["image"], "specs":{"gpu":terms["gpu_descriptor"]},
                 "price": terms["daily_bid_usd"], "creation_fee": terms["creation_fee_usd"],
                 "fee": 5, "spend": 0}
        self.orders.append(order)
        if self.mode == "timeout_after_create":
            raise TimeoutError("synthetic_timeout")
        return {"synthetic_order_id":order["id"]}


def verify_decision_for_simulation(telegram_db, nonce, now):
    """Read an exact acknowledged Telegram receipt (NOT a spend grant)."""
    if type(nonce) is not str or not re.fullmatch("[0-9a-f]{32}", nonce):
        raise GuardError("invalid_telegram_nonce")
    row = telegram_db.execute("""SELECT payload,payload_sha256,state,
                         message_id,expires_at,decided_at
                         FROM clore_telegram_offers WHERE nonce=?""",
                         (nonce,)).fetchone()
    if row is None:
        raise GuardError("missing_telegram_decision")
    payload, digest, state, message_id, expiry, decided_at = row
    if (state != "acknowledged" or type(message_id) is not int or message_id <= 0 or
            type(decided_at) is not int or type(expiry) is not int or
            not decided_at < expiry or not decided_at <= now < expiry or
            not hmac.compare_digest(hashlib.sha256(payload.encode()).hexdigest(),digest)):
        raise GuardError("untrusted_or_expired_telegram_decision")
    try:
        terms = json.loads(payload)
        current = validate_terms(terms,now)
    except (GuardError,ValueError,TypeError) as exc:
        raise GuardError("telegram_terms_expired_or_invalid") from exc
    if not hmac.compare_digest(current,payload):
        raise GuardError("noncanonical_telegram_terms")
    return terms,digest


def simulate_once(*, telegram_db, guard_db, nonce, provider, now):
    """Simulate: accepted quote -> reserved -> journal -> synthetic timeout.

    It never performs a real rental or binds/cancels an unknown order.
    NO production route calls this function.
    """
    if type(provider) is not SimulatedClore or type(now) is not int:
        raise GuardError("offline_simulator_only")
    terms,digest = verify_decision_for_simulation(telegram_db,nonce,now)
    hold = reserve(guard_db,terms=terms,api=provider,now=now,timer_check=True)
    rid=hold["reservation_id"]
    staged=stage_once(guard_db,reservation_id=rid,expected_digest=digest,
                      now=now,timer_check=True)
    assert staged["provider_request_made"] is False
    try:
        provider.simulated_create(terms,now)
    except TimeoutError:
        pass
    record_unknown(guard_db,reservation_id=rid,now=now+1)
    candidate=evaluate_candidate(guard_db,reservation_id=rid,api=provider,now=now+2)
    return {"simulation_only":True,"reservation_id":rid,
            "candidate_status":candidate["status"],
            "rental_permitted":False,"live_provider_mutations":0,
            "financial_lease_armed":False}
