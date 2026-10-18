"""Issue authorizations only inside the isolated, authenticated approval service.

The caller has to authenticate the human outside this component. This module
is not an HTTP handler, not a ChatGPT API and not safe to call from gpt-agent.
"""
import hashlib
import hmac
import secrets
from dataclasses import dataclass

from approval import Approval, _message, canonical_operation
from approval_store import ApprovalStore


@dataclass(frozen=True)
class VerifiedHuman:
    """Produced only by a trusted and already-verified identity provider."""
    subject_id: str
    authentication_time: int


def issue_approval(
    store: ApprovalStore,
    secret: bytes,
    operation: dict,
    *,
    principal: VerifiedHuman,
    expected_owner_id: str,
    backup_digest: str,
    now: int,
) -> Approval:
    """Sign and persist a narrowly scoped, short-lived approval.

    WARNING: VerifiedHuman is only a data class. A malicious caller can
    instantiate it. Enforce server-only invocation and trusted IdP validation.
    """
    if not isinstance(principal, VerifiedHuman) or principal.subject_id != expected_owner_id:
        raise PermissionError("Authenticated owner required")
    if principal.authentication_time > now or now - principal.authentication_time > 300:
        raise PermissionError("Recent authentication required")
    if not isinstance(secret, bytes) or len(secret) < 32:
        raise RuntimeError("Secure signing key missing")
    if len(backup_digest) != 64 or any(c not in "0123456789abcdef" for c in backup_digest):
        raise PermissionError("Verified backup digest required")
    digest = canonical_operation(operation)
    nonce = secrets.token_urlsafe(24)
    unsigned = Approval(digest, principal.subject_id, now + 300, nonce, backup_digest, "")
    signature = hmac.new(secret, _message(unsigned), hashlib.sha256).hexdigest()
    approval = Approval(digest, principal.subject_id, now + 300, nonce, backup_digest, signature)
    store.register(approval)
    return approval
