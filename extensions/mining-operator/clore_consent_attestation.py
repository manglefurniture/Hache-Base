#!/usr/bin/env python3
"""Offline Ed25519 proof of Clore Telegram consent. NO financial grant.

The Telegram signing key stays private to its service identity. The finance
watchdog receives only a public key and a detached, bounded consent receipt.
Neither component gains another user's database or provider credentials.
Nothing here creates, bids for, binds, or cancels a real order.
"""
import base64
import binascii
import hashlib
import hmac
import json
import re
import sqlite3
import time

from clore_cancel_guard import GuardError
from clore_preorder import supervisor_healthy, validate_terms

DOMAIN = "hache.clore.consent.v1"
AUDIENCE = "clore-financial-risk-ledger"
SCHEMA = """
CREATE TABLE IF NOT EXISTS clore_consent_receipts (
 nonce TEXT PRIMARY KEY,
 reservation_id TEXT NOT NULL UNIQUE,
 terms_sha256 TEXT NOT NULL,
 signature_sha256 TEXT NOT NULL,
 decided_at INTEGER NOT NULL,
 received_at INTEGER NOT NULL,
 state TEXT NOT NULL CHECK(state='verified_only')
);
"""


class ConsentError(ValueError):
    pass


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode("utf-8")


def digest_valid(s):
    return type(s) is str and re.fullmatch(r"[0-9a-f]{64}", s) is not None


def nonce_valid(s):
    return type(s) is str and re.fullmatch(r"[0-9a-f]{32}", s) is not None


def crypto():
    # An unavailable crypto provider is a hard failure; never fall back to
    # an unsigned approval or a shared HMAC secret.
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey, Ed25519PublicKey
        )
        from cryptography.hazmat.primitives.serialization import (
            Encoding, PublicFormat
        )
    except ImportError as exc:
        raise ConsentError("ed25519_dependency_missing") from exc
    return InvalidSignature, Ed25519PrivateKey, Ed25519PublicKey, Encoding, PublicFormat


def issue_receipt(telegram_db, *, nonce, private_key_raw, now=None):
    """Sign only an unexpired, exact owner-acknowledged row.

    Only called by a future separately authorized exporter; NOT connected
    to the running Telegram bot and not a spending entitlement.
    """
    now = int(time.time()) if now is None else now
    if type(now) is not int or not nonce_valid(nonce):
        raise ConsentError("invalid_issue_request")
    if type(private_key_raw) is not bytes or len(private_key_raw) != 32:
        raise ConsentError("invalid_signing_key")
    row = telegram_db.execute("""SELECT payload,payload_sha256,expires_at,state,
                                        message_id,decided_at
                                 FROM clore_telegram_offers WHERE nonce=?""",
                              (nonce,)).fetchone()
    if row is None:
        raise ConsentError("approval_not_found")
    raw, expected, expires, state, message_id, decided = row
    if (state != "acknowledged" or type(raw) is not str or
            not digest_valid(expected) or type(expires) is not int or
            type(decided) is not int or type(message_id) is not int or
            message_id <= 0 or not 0 < decided <= now < expires):
        raise ConsentError("consent_not_current_or_acknowledged")
    if not hmac.compare_digest(hashlib.sha256(raw.encode()).hexdigest(), expected):
        raise ConsentError("consent_payload_tampered")
    try:
        terms = json.loads(raw)
        recanonical = validate_terms(terms, now)
    except (ValueError, TypeError, GuardError) as exc:
        raise ConsentError("consent_terms_invalid") from exc
    if recanonical != raw:
        raise ConsentError("consent_payload_noncanonical")
    statement = {
        "domain": DOMAIN, "audience": AUDIENCE, "nonce": nonce,
        "terms_sha256": expected, "message_id": message_id,
        "decided_at": decided, "expires_at": expires
    }
    _, Private, _, Encoding, PublicFormat = crypto()
    private = Private.from_private_bytes(private_key_raw)
    public = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return {
        "statement": statement,
        "key_id": hashlib.sha256(public).hexdigest(),
        "signature": base64.b64encode(private.sign(canonical(statement))).decode("ascii")
    }


def verify_receipt(receipt, *, trusted_public_key_raw, now=None):
    """Require trust from external public key, never from receipt-supplied key."""
    now = int(time.time()) if now is None else now
    if (type(now) is not int or type(trusted_public_key_raw) is not bytes or
            len(trusted_public_key_raw) != 32 or type(receipt) is not dict or
            set(receipt) != {"statement", "key_id", "signature"}):
        raise ConsentError("invalid_signed_receipt")
    statement = receipt["statement"]
    if type(statement) is not dict or set(statement) != {
            "domain", "audience", "nonce", "terms_sha256", "message_id",
            "decided_at", "expires_at"}:
        raise ConsentError("invalid_consent_statement")
    if (statement["domain"] != DOMAIN or statement["audience"] != AUDIENCE or
            not nonce_valid(statement["nonce"]) or
            not digest_valid(statement["terms_sha256"]) or
            type(statement["message_id"]) is not int or statement["message_id"] <= 0 or
            type(statement["decided_at"]) is not int or
            type(statement["expires_at"]) is not int or
            not 0 < statement["decided_at"] <= now < statement["expires_at"] or
            statement["expires_at"] - statement["decided_at"] > 120):
        raise ConsentError("consent_expired_or_wrong_audience")
    actual_key_id = hashlib.sha256(trusted_public_key_raw).hexdigest()
    if type(receipt["key_id"]) is not str or not hmac.compare_digest(
            receipt["key_id"], actual_key_id):
        raise ConsentError("untrusted_signing_key")
    if type(receipt["signature"]) is not str or len(receipt["signature"]) > 100:
        raise ConsentError("invalid_receipt_signature")
    try:
        signature = base64.b64decode(receipt["signature"], validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ConsentError("invalid_receipt_signature") from exc
    if len(signature) != 64:
        raise ConsentError("invalid_receipt_signature")
    InvalidSignature, _, Public, _, _ = crypto()
    try:
        Public.from_public_bytes(trusted_public_key_raw).verify(
            signature, canonical(statement))
    except (InvalidSignature, ValueError) as exc:
        raise ConsentError("bad_consent_signature") from exc
    # Fresh trusted key and exact canonical signed statement, but still NOT a
    # financial authorization. The risk ledger must independently gate it.
    return statement


def init_ledger_schema(guard_db):
    if guard_db.in_transaction:
        raise ConsentError("schema_requires_no_transaction")
    guard_db.executescript(SCHEMA)


def record_verified_consent(guard_db, *, receipt, trusted_public_key_raw,
                            reservation_id, now=None, timer_check=False):
    """One-use matching receipt, stored by the financial user in its own DB.

    Does not create a provider order or a spend grant; its only state change
    is an attested audit row. No Telegram DB access is needed.
    """
    now = int(time.time()) if now is None else now
    if type(now) is not int or not nonce_valid(reservation_id):
        raise ConsentError("invalid_consent_enrollment")
    verified = verify_receipt(receipt, trusted_public_key_raw=trusted_public_key_raw,
                              now=now)
    supervisor_healthy(guard_db, now, timer_check)
    if not guard_db.execute("""SELECT 1 FROM sqlite_master
              WHERE type='table' AND name='clore_consent_receipts'""").fetchone():
        raise ConsentError("consent_ledger_schema_missing")
    guard_db.execute("BEGIN IMMEDIATE")
    try:
        row = guard_db.execute("""SELECT terms_json,terms_sha256,phase,outcome,
                                          created_at,expires_at
                 FROM clore_preorders WHERE reservation_id=?""",
                 (reservation_id,)).fetchone()
        if row is None:
            raise ConsentError("unreserved_clore_terms")
        raw, terms_sha, phase, outcome, created, expires = row
        if (type(raw) is not str or not digest_valid(terms_sha) or
                not hmac.compare_digest(hashlib.sha256(raw.encode()).hexdigest(),terms_sha) or
                not hmac.compare_digest(terms_sha,verified["terms_sha256"]) or
                phase != "reserved" or outcome != "create_not_enabled" or
                not created <= now < expires):
            raise ConsentError("unapproved_or_stale_reservation")
        if guard_db.execute("SELECT 1 FROM clore_cancel_leases WHERE phase='armed' LIMIT 1").fetchone():
            raise ConsentError("existing_clore_financial_obligation")
        if guard_db.execute("""SELECT 1 FROM clore_consent_receipts
                                WHERE nonce=? OR reservation_id=? LIMIT 1""",
                            (verified["nonce"], reservation_id)).fetchone():
            raise ConsentError("consent_receipt_already_used")
        try:
            guard_db.execute("""INSERT INTO clore_consent_receipts
               (nonce,reservation_id,terms_sha256,signature_sha256,
                decided_at,received_at,state) VALUES (?,?,?,?,?,?,'verified_only')""",
               (verified["nonce"],reservation_id,terms_sha,
                hashlib.sha256(base64.b64decode(receipt["signature"])).hexdigest(),
                verified["decided_at"],now))
        except sqlite3.IntegrityError as exc:
            raise ConsentError("consent_receipt_already_used") from exc
        guard_db.commit()
    except Exception:
        guard_db.rollback()
        raise
    return {"consent_recorded": True, "reservation_id": reservation_id,
            "rental_permitted": False, "provider_mutation": False}
