"""Approval verification library for a separate trusted approval gateway.

Only the gateway may create signed grants. The GPT agent must never have the
signing secret or direct access to the privileged database executor.
"""
import hashlib
import hmac
import json
import time
from dataclasses import dataclass


def canonical_operation(payload: dict) -> str:
    fields = {"database", "table", "operation", "where", "values"}
    if set(payload) != fields:
        raise ValueError("Unexpected operation fields")
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


@dataclass(frozen=True)
class Approval:
    operation_digest: str
    approver_id: str
    expires_at: int
    nonce: str
    backup_digest: str
    signature: str


def _message(a: Approval) -> bytes:
    return json.dumps({
        "operation_digest": a.operation_digest,
        "approver_id": a.approver_id,
        "expires_at": a.expires_at,
        "nonce": a.nonce,
        "backup_digest": a.backup_digest,
    }, sort_keys=True, separators=(",", ":")).encode()


def verify_approval(
    approval: Approval,
    operation: dict,
    secret: bytes,
    used_nonces: set[str],
    *,
    now: int | None = None,
) -> bool:
    """Pure validation. Nonce consumption must be atomic in a durable store."""
    instant = int(time.time()) if now is None else now
    if not secret or len(secret) < 32 or instant >= approval.expires_at:
        return False
    if approval.expires_at > instant + 300:
        return False
    if not approval.approver_id or not approval.nonce or approval.nonce in used_nonces:
        return False
    if not approval.backup_digest or len(approval.backup_digest) != 64:
        return False
    try:
        digest = canonical_operation(operation)
    except (TypeError, ValueError):
        return False
    if not hmac.compare_digest(approval.operation_digest, digest):
        return False
    expected = hmac.new(secret, _message(approval), hashlib.sha256).hexdigest()
    return hmac.compare_digest(approval.signature, expected)
