"""Persistent passkey ceremonies for an isolated SQL Guard approval service.

Never expose this store or the signing key to the GPT agent. The human signs
a request-specific WebAuthn challenge on an HTTPS origin (not a chat message).
"""
import hashlib
import hmac
import json
import secrets
import sqlite3
from dataclasses import asdict
from urllib.parse import urlparse

from webauthn import (
    base64url_to_bytes,
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria, PublicKeyCredentialDescriptor,
    ResidentKeyRequirement, UserVerificationRequirement,
)

from approval import Approval, _message, canonical_operation


class CeremonyRejected(PermissionError):
    pass


class PasskeyGateway:
    def __init__(self, database_path: str, *, rp_id: str, origin: str, owner_id: str,
                 signing_key: bytes, bootstrap_hash: str):
        parsed = urlparse(origin)
        if parsed.scheme != "https" or parsed.hostname != rp_id or parsed.path not in ("", "/"):
            raise ValueError("Origin must be exactly https://<rp_id>")
        if len(signing_key) < 32 or len(bootstrap_hash) != 64 or not owner_id:
            raise ValueError("Missing secured production configuration")
        self.rp_id, self.origin, self.owner_id = rp_id, origin.rstrip("/"), owner_id
        self.signing_key, self.bootstrap_hash = signing_key, bootstrap_hash
        self.db = sqlite3.connect(database_path, isolation_level=None, timeout=10)
        self.db.execute("PRAGMA busy_timeout=10000")
        self.db.execute("""CREATE TABLE IF NOT EXISTS passkeys (
            credential_id BLOB PRIMARY KEY, public_key BLOB NOT NULL,
            sign_count INTEGER NOT NULL)""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS requests (
            id TEXT PRIMARY KEY, operation_json TEXT NOT NULL,
            backup_digest TEXT NOT NULL, expires INTEGER NOT NULL,
            approved INTEGER NOT NULL DEFAULT 0)""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS ceremonies (
            challenge BLOB PRIMARY KEY, kind TEXT NOT NULL,
            request_id TEXT NOT NULL, expires INTEGER NOT NULL)""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS approvals (
            nonce TEXT PRIMARY KEY, payload TEXT NOT NULL,
            used INTEGER NOT NULL DEFAULT 0)""")

    def close(self):
        self.db.close()

    def _passkeys(self):
        return self.db.execute("SELECT credential_id,public_key,sign_count FROM passkeys").fetchall()

    def begin_enrollment(self, bootstrap_token: str, now: int) -> dict:
        if not hmac.compare_digest(hashlib.sha256(bootstrap_token.encode()).hexdigest(),
                                   self.bootstrap_hash):
            raise CeremonyRejected("Invalid enrollment authorization")
        if self._passkeys():
            raise CeremonyRejected("Owner already enrolled; separate recovery required")
        opts = generate_registration_options(
            rp_id=self.rp_id, rp_name="Hache SQL Guard",
            user_name="sqlguard-owner",
            user_id=hashlib.sha256(self.owner_id.encode()).digest()[:16],
            authenticator_selection=AuthenticatorSelectionCriteria(
                resident_key=ResidentKeyRequirement.PREFERRED,
                user_verification=UserVerificationRequirement.REQUIRED),
        )
        self.db.execute("INSERT INTO ceremonies VALUES (?,?,?,?)",
                        (opts.challenge, "enroll", "", now + 180))
        return json.loads(options_to_json(opts))

    def finish_enrollment(self, challenge_text: str, credential: dict, now: int) -> bool:
        challenge = base64url_to_bytes(challenge_text)
        try:
            self.db.execute("BEGIN IMMEDIATE")
            row = self.db.execute("SELECT expires FROM ceremonies WHERE challenge=? AND kind='enroll'",
                                  (challenge,)).fetchone()
            if not row or row[0] <= now or self._passkeys():
                raise CeremonyRejected("Invalid or expired enrollment")
            v = verify_registration_response(
                credential=credential, expected_challenge=challenge,
                expected_rp_id=self.rp_id, expected_origin=self.origin,
                require_user_verification=True)
            self.db.execute("INSERT INTO passkeys VALUES (?,?,?)",
                            (v.credential_id, v.credential_public_key, v.sign_count))
            self.db.execute("DELETE FROM ceremonies WHERE challenge=?", (challenge,))
            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            raise

    def stage_request(self, operation: dict, backup_digest: str, now: int) -> str:
        """ONLY called after authenticating agent. backup_digest is NOT proof of backup."""
        canonical_operation(operation)
        if (operation["operation"] not in ("update", "delete")
                or not isinstance(operation["where"], dict)
                or not operation["where"]
                or not isinstance(operation["values"], dict)
                or (operation["operation"] == "update" and not operation["values"])
                or (operation["operation"] == "delete" and operation["values"])
                or type(operation.get("expected_rows")) is not int
                or not 1 <= operation["expected_rows"] <= 1000
                or not isinstance(operation.get("expected_primary_keys"), list)
                or len(operation["expected_primary_keys"]) != operation["expected_rows"]):
            raise ValueError("Only scoped, explicitly counted UPDATE/DELETE can be approved")
        if len(backup_digest) != 64 or any(c not in "0123456789abcdef" for c in backup_digest):
            raise ValueError("Invalid backup checksum")
        request_id = secrets.token_urlsafe(24)
        self.db.execute("INSERT INTO requests VALUES (?,?,?,?,0)", (
            request_id,
            json.dumps(operation, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
            backup_digest, now + 300))
        return request_id

    def pending(self, request_id: str, now: int) -> dict:
        row = self.db.execute("SELECT operation_json,expires,approved FROM requests WHERE id=?",
                              (request_id,)).fetchone()
        if not row or row[1] <= now or row[2]:
            raise CeremonyRejected("Request unavailable")
        return json.loads(row[0])

    def begin_approval(self, request_id: str, now: int) -> dict:
        self.pending(request_id, now)
        credentials = self._passkeys()
        if not credentials:
            raise CeremonyRejected("Owner passkey not registered")
        opts = generate_authentication_options(
            rp_id=self.rp_id,
            allow_credentials=[PublicKeyCredentialDescriptor(id=r[0]) for r in credentials],
            user_verification=UserVerificationRequirement.REQUIRED)
        self.db.execute("INSERT INTO ceremonies VALUES (?,?,?,?)",
                        (opts.challenge, "approve", request_id, min(now + 180, now + 300)))
        return json.loads(options_to_json(opts))

    def finish_approval(self, request_id: str, challenge_text: str, credential: dict,
                        now: int, *, backup_is_verified: bool = False) -> str:
        """Issue and persist exactly one grant under one transaction.

        backup_is_verified must come from an independent trusted service, never
        from agent input or the browser. Returns a nonce, not the signed token.
        """
        if backup_is_verified is not True:
            raise CeremonyRejected("Independent backup verification required")
        challenge = base64url_to_bytes(challenge_text)
        try:
            self.db.execute("BEGIN IMMEDIATE")
            row = self.db.execute(
                "SELECT operation_json,backup_digest,expires,approved FROM requests WHERE id=?",
                (request_id,)).fetchone()
            ceremony = self.db.execute(
                "SELECT expires FROM ceremonies WHERE challenge=? AND kind='approve' AND request_id=?",
                (challenge, request_id)).fetchone()
            if not row or row[2] <= now or row[3] or not ceremony or ceremony[0] <= now:
                raise CeremonyRejected("Request or challenge expired")
            credential_id = base64url_to_bytes(credential["rawId"])
            key = self.db.execute(
                "SELECT public_key,sign_count FROM passkeys WHERE credential_id=?",
                (credential_id,)).fetchone()
            if not key:
                raise CeremonyRejected("Unknown credential")
            result = verify_authentication_response(
                credential=credential, expected_challenge=challenge,
                expected_rp_id=self.rp_id, expected_origin=self.origin,
                credential_public_key=key[0], credential_current_sign_count=key[1],
                require_user_verification=True)
            operation = json.loads(row[0])
            nonce = secrets.token_urlsafe(24)
            approval = Approval(canonical_operation(operation), self.owner_id,
                                min(now + 180, row[2]), nonce, row[1], "")
            signature = hmac.new(self.signing_key, _message(approval), hashlib.sha256).hexdigest()
            signed = Approval(approval.operation_digest, approval.approver_id,
                              approval.expires_at, approval.nonce, approval.backup_digest,
                              signature)
            self.db.execute("INSERT INTO approvals VALUES (?,?,0)",
                            (nonce, json.dumps(asdict(signed), sort_keys=True)))
            self.db.execute("UPDATE requests SET approved=1 WHERE id=? AND approved=0",
                            (request_id,))
            self.db.execute("UPDATE passkeys SET sign_count=? WHERE credential_id=?",
                            (result.new_sign_count, credential_id))
            self.db.execute("DELETE FROM ceremonies WHERE challenge=?", (challenge,))
            self.db.commit()
            return nonce
        except Exception:
            self.db.rollback()
            raise
