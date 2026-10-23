#!/usr/bin/env python3
"""Read-only watchdog recovery for a potential Clore create_order timeout.

No create/cancel/bid API, grant generation or automatic lease binding.
An unbound order is a financial emergency, never equivalent to an idle guard.
"""
import re
import time
from clore_cancel_guard import GuardError, heartbeat
from clore_preorder import evaluate_candidate

SCHEMA = """
CREATE TABLE IF NOT EXISTS clore_pending_recovery(
 reservation_id TEXT PRIMARY KEY,
 checked_at INTEGER NOT NULL,
 status TEXT NOT NULL,
 candidate_order_id INTEGER,
 FOREIGN KEY(reservation_id) REFERENCES clore_preorders(reservation_id)
);
"""

def pending(db):
    exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                        "AND name='clore_preorders'").fetchone()
    if not exists:
        return []
    return db.execute("""SELECT reservation_id,phase,outcome,created_at
       FROM clore_preorders WHERE phase='uncertain'
       ORDER BY created_at""").fetchall()

def inspect(db, api, *, now=None):
    """Persist sanitized reconciliation evidence. Always fail financially closed.

    A single matching candidate is NOT proof it was our order and MUST NOT
    trigger an unauthorized cancellation or financial lease.
    """
    now = int(time.time()) if now is None else int(now)
    rows = pending(db)
    if not rows:
        return None
    if len(rows) != 1:
        raise GuardError("multiple_uncertain_clore_preorders")
    rid, phase, outcome, created_at = rows[0]
    if (type(rid) is not str or not re.fullmatch(r"[0-9a-f]{32}", rid) or
            phase != "uncertain" or type(outcome) is not str or
            outcome not in ("create_submitted_once", "create_response_unknown")):
        raise GuardError("untrusted_uncertain_preorder_state")
    # This is one authenticated provider GET through evaluate_candidate().
    result = evaluate_candidate(db, reservation_id=rid, api=api, now=now)
    status = result["status"]
    if status not in ("not_found", "ambiguous", "unrelated_new_order",
                      "identity_mismatch", "price_or_fee_mismatch",
                      "candidate_unbound"):
        raise GuardError("invalid_reconciliation_result")
    candidate = result.get("candidate_order_id")
    if candidate is not None and (type(candidate) is not int or candidate <= 0):
        raise GuardError("invalid_candidate_id")
    db.execute("BEGIN IMMEDIATE")
    try:
        row = db.execute("""SELECT phase,outcome FROM clore_preorders
              WHERE reservation_id=?""", (rid,)).fetchone()
        if row is None or row[0] != "uncertain" or row[1] != outcome:
            raise GuardError("pending_state_changed")
        db.executescript("") if False else None  # schema migration handled outside transaction
        db.execute("""INSERT INTO clore_pending_recovery
            (reservation_id,checked_at,status,candidate_order_id)
            VALUES(?,?,?,?) ON CONFLICT(reservation_id) DO UPDATE SET
              checked_at=excluded.checked_at,status=excluded.status,
              candidate_order_id=excluded.candidate_order_id""",
            (rid, now, status, candidate))
        heartbeat(db, now)  # authenticated read succeeded
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"status": "possible_unprotected_clore_order",
            "reconciliation": status, "candidate_order_id": candidate,
            "rental_permitted": False, "requires_manual_review": True}

def inspect_and_alert(db, api, *, now=None):
    if not pending(db):
        return None
    # Prepare schema before starting the data transaction (executescript
    # would otherwise implicitly commit it).
    db.executescript(SCHEMA)
    result = inspect(db, api, now=now)
    if result is not None:
        raise GuardError("possible_unprotected_clore_order")
    return None
