#!/usr/bin/env python3
"""Write-ahead risk journal for a *future* authorized Clore create attempt.

No provider POST, budget grant, root access, credential or commercial action.
This journal deliberately marks financial exposure as UNCERTAIN *before*
an eventual external request; only a separate, audited executor could issue
one later. A durable journal entry is NOT sufficient rental authorization.
"""
import hashlib
import hmac
import re
import sqlite3
import time

from clore_cancel_guard import GuardError
from clore_preorder import BLOCKING_PHASES, supervisor_healthy

SCHEMA = """
CREATE TABLE IF NOT EXISTS clore_create_attempts(
 reservation_id TEXT PRIMARY KEY,
 terms_sha256 TEXT NOT NULL,
 marked_at INTEGER NOT NULL,
 outcome TEXT NOT NULL CHECK(outcome IN
    ('create_submitted_once','create_response_unknown')),
 checked_at INTEGER,
 FOREIGN KEY(reservation_id) REFERENCES clore_preorders(reservation_id)
);
"""


def init_schema(db):
    # Only run outside transactions: sqlite executescript implicitly commits.
    if db.in_transaction:
        raise GuardError("schema_requires_no_transaction")
    db.executescript(SCHEMA)


def stage_once(db, *, reservation_id, expected_digest, now=None,
               timer_check=False):
    """Durably mark possible spend, no later than the original reservation.

    The call is a risk-state transition, never a permission to send a POST.
    The future sender MUST verify a separate authenticated one-use grant.
    No code path in this module ever calls the provider.
    """
    now = int(time.time()) if now is None else now
    if type(now) is not int or now < 0:
        raise GuardError("invalid_journal_time")
    if type(reservation_id) is not str or not re.fullmatch(r"[0-9a-f]{32}", reservation_id):
        raise GuardError("invalid_reservation_id")
    if type(expected_digest) is not str or not re.fullmatch(r"[0-9a-f]{64}", expected_digest):
        raise GuardError("invalid_terms_digest")
    supervisor_healthy(db, now, timer_check)
    # Fail closed if the migration is missing; never apply runtime DDL here.
    if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='clore_create_attempts'").fetchone():
        raise GuardError("journal_schema_missing")
    db.execute("BEGIN IMMEDIATE")
    try:
        row = db.execute("""SELECT terms_json,terms_sha256,created_at,expires_at,phase,outcome
               FROM clore_preorders WHERE reservation_id=?""",
               (reservation_id,)).fetchone()
        if row is None:
            raise GuardError("reservation_missing")
        payload, digest, created, expiry, phase, outcome = row
        if not (hmac.compare_digest(hashlib.sha256(payload.encode()).hexdigest(), digest)
                and hmac.compare_digest(digest, expected_digest)):
            raise GuardError("reservation_terms_mismatch")
        if phase != "reserved" or outcome != "create_not_enabled":
            raise GuardError("create_already_staged_or_reservation_invalid")
        if not created <= now < expiry:
            raise GuardError("reservation_window_closed")
        if db.execute("SELECT 1 FROM clore_cancel_leases WHERE phase='armed' LIMIT 1").fetchone():
            raise GuardError("existing_financial_lease")
        if db.execute("""SELECT 1 FROM clore_create_attempts
                         WHERE reservation_id=?""",(reservation_id,)).fetchone():
            raise GuardError("create_attempt_already_recorded")
        db.execute("""INSERT INTO clore_create_attempts
              (reservation_id,terms_sha256,marked_at,outcome)
              VALUES(?,?,?,'create_submitted_once')""",
              (reservation_id,digest,now))
        changed=db.execute("""UPDATE clore_preorders SET phase='uncertain',
                 outcome='create_submitted_once'
                 WHERE reservation_id=? AND phase='reserved'
                   AND outcome='create_not_enabled'""",(reservation_id,)).rowcount
        if changed != 1:
            raise GuardError("reservation_state_changed")
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"reservation_id":reservation_id,"status":"possible_external_spend",
            "provider_request_made":False,"rental_permitted":False}


def record_unknown(db, *, reservation_id, now=None):
    """A timeout/error never releases a pre-create budget reservation."""
    now = int(time.time()) if now is None else now
    if type(now) is not int or now < 0 or type(reservation_id) is not str or not re.fullmatch("[0-9a-f]{32}",reservation_id):
        raise GuardError("invalid_unknown_response")
    db.execute("BEGIN IMMEDIATE")
    try:
        row=db.execute("""SELECT p.phase,p.outcome,j.outcome
          FROM clore_preorders p JOIN clore_create_attempts j USING(reservation_id)
          WHERE p.reservation_id=?""",(reservation_id,)).fetchone()
        if row is None or row[0]!="uncertain" or row[1] not in (
                "create_submitted_once","create_response_unknown") or row[2] not in (
                "create_submitted_once","create_response_unknown"):
            raise GuardError("no_staged_create_attempt")
        db.execute("""UPDATE clore_preorders SET outcome='create_response_unknown'
          WHERE reservation_id=?""",(reservation_id,))
        db.execute("""UPDATE clore_create_attempts SET outcome='create_response_unknown',
                  checked_at=? WHERE reservation_id=?""",(now,reservation_id))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"status":"unresolved_external_spend","rental_permitted":False}


def status(db,reservation_id):
    row=db.execute("""SELECT outcome,marked_at,checked_at FROM clore_create_attempts
                      WHERE reservation_id=?""",(reservation_id,)).fetchone()
    if row is None:
        return {"status":"not_staged","rental_permitted":False}
    return {"status":row[0],"marked_at":row[1],"checked_at":row[2],
            "rental_permitted":False}
