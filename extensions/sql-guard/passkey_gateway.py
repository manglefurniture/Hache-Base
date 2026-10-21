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
            approved INTEGER NOT NULL DEFAULT 0,
            approval_nonce TEXT)""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS ceremonies (
            challenge BLOB PRIMARY KEY, kind TEXT NOT NULL,
            request_id TEXT NOT NULL, expires INTEGER NOT NULL)""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS approvals (
            nonce TEXT PRIMARY KEY, payload TEXT NOT NULL,
            used INTEGER NOT NULL DEFAULT 0)""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS stage_budget (
            window_type TEXT NOT NULL, window_id INTEGER NOT NULL,
            requests INTEGER NOT NULL,
            PRIMARY KEY (window_type,window_id))""")

    def close(self):
        self.db.close()

    def _passkeys(self):
        return self.db.execute("SELECT credential_id,public_key,sign_count FROM passkeys").fetchall()

    def _purge_expired(self, now: int):
        """Called inside a write transaction; do not retain expired untrusted blobs."""
        self.db.execute("DELETE FROM ceremonies WHERE expires<=?", (now,))
        self.db.execute("DELETE FROM requests WHERE expires<=?", (now,))
        self.db.execute(
            "DELETE FROM stage_budget WHERE "
            "(window_type='hour' AND window_id<?) OR "
            "(window_type='day' AND window_id<?)",
            (now // 3600 - 48, now // 86400 - 2))

    def _charge_stage_budget(self, now: int):
        """Durable global limits, charged atomically with the staged request."""
        for kind, window, cap in (
                ("hour", now // 3600, 20), ("day", now // 86400, 100)):
            self.db.execute(
                "INSERT OR IGNORE INTO stage_budget VALUES (?,?,0)", (kind, window))
            changed = self.db.execute(
                "UPDATE stage_budget SET requests=requests+1 "
                "WHERE window_type=? AND window_id=? AND requests<?",
                (kind, window, cap)).rowcount
            if changed != 1:
                raise CeremonyRejected("Request staging quota exhausted")

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
        self.db.execute("DELETE FROM ceremonies WHERE expires<=?", (now,))
        if self.db.execute(
                "SELECT COUNT(*) FROM ceremonies WHERE kind='enroll'"
        ).fetchone()[0] >= 3:
            raise CeremonyRejected("Too many enrollment ceremonies")
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

    def begin_passkey_check(self, now: int) -> dict:
        """Owner-only authentication ceremony; creates NO operation or grant."""
        try:
            self.db.execute("BEGIN IMMEDIATE")
            self._purge_expired(now)
            credentials = self._passkeys()
            if len(credentials) != 1:
                raise CeremonyRejected("Exactly one owner passkey required")
            if self.db.execute(
                "SELECT COUNT(*) FROM ceremonies WHERE kind='passkey_check'"
            ).fetchone()[0] >= 3:
                raise CeremonyRejected("Too many active verification ceremonies")
            hour = now // 3600
            self.db.execute(
                "DELETE FROM stage_budget WHERE window_type='passkey_check_hour' "
                "AND window_id<?", (hour - 24,))
            self.db.execute(
                "INSERT OR IGNORE INTO stage_budget VALUES ('passkey_check_hour',?,0)",
                (hour,))
            charged = self.db.execute(
                "UPDATE stage_budget SET requests=requests+1 "
                "WHERE window_type='passkey_check_hour' AND window_id=? AND requests<6",
                (hour,)).rowcount
            if charged != 1:
                raise CeremonyRejected("Hourly passkey verification limit reached")
            options = generate_authentication_options(
                rp_id=self.rp_id,
                allow_credentials=[PublicKeyCredentialDescriptor(id=credentials[0][0])],
                user_verification=UserVerificationRequirement.REQUIRED)
            self.db.execute(
                "INSERT INTO ceremonies VALUES (?,?,?,?)",
                (options.challenge, "passkey_check", "", now + 120))
            self.db.commit()
            return json.loads(options_to_json(options))
        except Exception:
            self.db.rollback()
            raise

    def finish_passkey_check(self, challenge_text: str, credential: dict,
                             now: int) -> bool:
        """Verify owner signature but do not issue approvals or authorization nonces."""
        if not isinstance(credential, dict) or not isinstance(credential.get("rawId"), str):
            raise CeremonyRejected("Missing passkey credential")
        try:
            challenge = base64url_to_bytes(challenge_text)
        except Exception as exc:
            raise CeremonyRejected("Invalid verification challenge") from exc
        try:
            self.db.execute("BEGIN IMMEDIATE")
            row = self.db.execute(
                "SELECT expires FROM ceremonies "
                "WHERE challenge=? AND kind='passkey_check'",
                (challenge,)).fetchone()
            if not row or row[0] <= now:
                raise CeremonyRejected("Unknown or expired verification challenge")
            credential_id = base64url_to_bytes(credential["rawId"])
            stored = self.db.execute(
                "SELECT public_key,sign_count FROM passkeys WHERE credential_id=?",
                (credential_id,)).fetchone()
            if not stored:
                raise CeremonyRejected("Unknown owner credential")
            try:
                result = verify_authentication_response(
                    credential=credential,
                    expected_challenge=challenge,
                    expected_rp_id=self.rp_id,
                    expected_origin=self.origin,
                    credential_public_key=stored[0],
                    credential_current_sign_count=stored[1],
                    require_user_verification=True)
            except Exception as exc:
                raise CeremonyRejected("Invalid passkey signature") from exc
            self.db.execute(
                "UPDATE passkeys SET sign_count=? WHERE credential_id=?",
                (result.new_sign_count, credential_id))
            self.db.execute(
                "DELETE FROM ceremonies WHERE challenge=? AND kind='passkey_check'",
                (challenge,))
            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            raise


    def begin_root_window(self, action: str, now: int) -> dict:
        """New passkey assertion, cryptographically bound to enable OR disable."""
        if action not in ("enable", "disable"):
            raise CeremonyRejected("Invalid window action")
        try:
            self.db.execute("BEGIN IMMEDIATE")
            self._purge_expired(now)
            keys = self._passkeys()
            if len(keys) != 1:
                raise CeremonyRejected("Exactly one owner passkey required")
            if self.db.execute("SELECT COUNT(*) FROM ceremonies WHERE kind LIKE 'root_window_%'").fetchone()[0] >= 3:
                raise CeremonyRejected("Too many window ceremonies")
            hour = now // 3600
            self.db.execute("DELETE FROM stage_budget WHERE window_type='root_window_hour' AND window_id<?", (hour-48,))
            self.db.execute("INSERT OR IGNORE INTO stage_budget VALUES ('root_window_hour',?,0)", (hour,))
            if self.db.execute("UPDATE stage_budget SET requests=requests+1 WHERE window_type='root_window_hour' AND window_id=? AND requests<6", (hour,)).rowcount != 1:
                raise CeremonyRejected("Window rate limited")
            opts = generate_authentication_options(
                rp_id=self.rp_id,
                allow_credentials=[PublicKeyCredentialDescriptor(id=keys[0][0])],
                user_verification=UserVerificationRequirement.REQUIRED)
            self.db.execute("INSERT INTO ceremonies VALUES (?,?,?,?)",
                            (opts.challenge, "root_window_" + action, action, now + 120))
            self.db.commit()
            return json.loads(options_to_json(opts))
        except Exception:
            self.db.rollback()
            raise

    def finish_root_window(self, action: str, challenge_text: str, credential: dict,
                           now: int, *, window_key: bytes) -> dict:
        """Credential stays in independent approval store; ticket is short lived."""
        if action not in ("enable","disable") or len(window_key) != 32:
            raise CeremonyRejected("Window unavailable")
        if not isinstance(credential, dict) or not isinstance(credential.get("rawId"), str):
            raise CeremonyRejected("Invalid credential")
        try:
            challenge = base64url_to_bytes(challenge_text)
            credential_id = base64url_to_bytes(credential["rawId"])
        except Exception as exc:
            raise CeremonyRejected("Invalid challenge") from exc
        try:
            self.db.execute("BEGIN IMMEDIATE")
            row = self.db.execute(
                "SELECT expires FROM ceremonies WHERE challenge=? AND kind=? AND request_id=?",
                (challenge, "root_window_" + action, action)).fetchone()
            if not row or row[0] <= now:
                raise CeremonyRejected("Expired ceremony")
            key = self.db.execute("SELECT public_key,sign_count FROM passkeys WHERE credential_id=?",
                                  (credential_id,)).fetchone()
            if not key:
                raise CeremonyRejected("Unknown owner credential")
            try:
                verified = verify_authentication_response(
                    credential=credential, expected_challenge=challenge,
                    expected_rp_id=self.rp_id, expected_origin=self.origin,
                    credential_public_key=key[0], credential_current_sign_count=key[1],
                    require_user_verification=True)
            except Exception as exc:
                raise CeremonyRejected("Invalid owner assertion") from exc
            payload = {
                "domain":"hache-root-window/v1", "scope":"restart_operator",
                "action":action, "duration_sec":600 if action=="enable" else 0,
                "expires_at":now+30, "nonce":secrets.token_urlsafe(32)
            }
            message = json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()
            signature = hmac.new(window_key,message,hashlib.sha256).hexdigest()
            if self.db.execute("DELETE FROM ceremonies WHERE challenge=? AND kind=? AND request_id=?",
                               (challenge,"root_window_"+action,action)).rowcount != 1:
                raise CeremonyRejected("Ceremony already consumed")
            self.db.execute("UPDATE passkeys SET sign_count=? WHERE credential_id=?",
                            (verified.new_sign_count,credential_id))
            self.db.commit()
            return {"payload":payload,"signature":signature}
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
        operation_json = json.dumps(
            operation, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        if len(operation_json.encode("utf-8")) > 8192:
            raise ValueError("Staged operation is too large")
        request_id = secrets.token_urlsafe(24)
        try:
            self.db.execute("BEGIN IMMEDIATE")
            self._purge_expired(now)
            if self.db.execute(
                    "SELECT COUNT(*) FROM requests"
            ).fetchone()[0] >= 30:
                raise CeremonyRejected("Too many live requests")
            self._charge_stage_budget(now)
            self.db.execute(
                "INSERT INTO requests "
                "(id,operation_json,backup_digest,expires,approved,approval_nonce) "
                "VALUES (?,?,?,?,0,NULL)",
                (request_id, operation_json, backup_digest, now + 300))
            self.db.commit()
            return request_id
        except Exception:
            self.db.rollback()
            raise

    def pending(self, request_id: str, now: int) -> dict:
        row = self.db.execute("SELECT operation_json,expires,approved FROM requests WHERE id=?",
                              (request_id,)).fetchone()
        if not row or row[1] <= now or row[2]:
            raise CeremonyRejected("Request unavailable")
        return json.loads(row[0])

    def begin_approval(self, request_id: str, now: int) -> dict:
        try:
            self.db.execute("BEGIN IMMEDIATE")
            self._purge_expired(now)
            self.pending(request_id, now)
            if self.db.execute(
                    "SELECT COUNT(*) FROM ceremonies WHERE kind='approve' "
                    "AND request_id=?", (request_id,)
            ).fetchone()[0] >= 3:
                raise CeremonyRejected("Too many active approval ceremonies")
            credentials = self._passkeys()
            if not credentials:
                raise CeremonyRejected("Owner passkey not registered")
            opts = generate_authentication_options(
                rp_id=self.rp_id,
                allow_credentials=[
                    PublicKeyCredentialDescriptor(id=r[0]) for r in credentials],
                user_verification=UserVerificationRequirement.REQUIRED)
            self.db.execute("INSERT INTO ceremonies VALUES (?,?,?,?)",
                            (opts.challenge, "approve", request_id, now + 180))
            self.db.commit()
            return json.loads(options_to_json(opts))
        except Exception:
            self.db.rollback()
            raise

    def finish_approval(self, request_id: str, challenge_text: str, credential: dict,
                        now: int, *, backup_checker=None) -> str:
        """Verify the passkey BEFORE expensive independent backup verification.

        The trusted checker is server-side only, never provided by the agent
        or browser. All checks and grant issuance happen under one transaction.
        """
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
            try:
                result = verify_authentication_response(
                    credential=credential, expected_challenge=challenge,
                    expected_rp_id=self.rp_id, expected_origin=self.origin,
                    credential_public_key=key[0], credential_current_sign_count=key[1],
                    require_user_verification=True)
            except Exception as exc:
                raise CeremonyRejected("Invalid passkey assertion") from exc
            operation = json.loads(row[0])
            if backup_checker is None or backup_checker(operation, row[1]) is not True:
                raise CeremonyRejected("Independent backup verification required")
            nonce = secrets.token_urlsafe(24)
            approval = Approval(canonical_operation(operation), self.owner_id,
                                min(now + 180, row[2]), nonce, row[1], "")
            signature = hmac.new(self.signing_key, _message(approval), hashlib.sha256).hexdigest()
            signed = Approval(approval.operation_digest, approval.approver_id,
                              approval.expires_at, approval.nonce, approval.backup_digest,
                              signature)
            self.db.execute("INSERT INTO approvals VALUES (?,?,0)",
                            (nonce, json.dumps(asdict(signed), sort_keys=True)))
            updated = self.db.execute(
                "UPDATE requests SET approved=1,approval_nonce=? "
                "WHERE id=? AND approved=0", (nonce, request_id)).rowcount
            if updated != 1:
                raise CeremonyRejected("Approval was already completed")
            self.db.execute("UPDATE passkeys SET sign_count=? WHERE credential_id=?",
                            (result.new_sign_count, credential_id))
            self.db.execute("DELETE FROM ceremonies WHERE challenge=?", (challenge,))
            self.db.commit()
            return nonce
        except Exception:
            self.db.rollback()
            raise
