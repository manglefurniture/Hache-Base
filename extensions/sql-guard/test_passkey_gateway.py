import hashlib
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from webauthn import base64url_to_bytes
from passkey_gateway import CeremonyRejected, PasskeyGateway

SECRET = b"super-secret-approval-gateway-key-with-entropy"
TOKEN = "human-out-of-band-bootstrap-token"
OP = {"database":"sandbox","table":"items","operation":"delete","where":{"id":1},"values":{},"expected_rows":1,"expected_primary_keys":[1]}


class PasskeyGatewayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "gateway.sqlite")
        self.db = self.gateway()

    def gateway(self):
        return PasskeyGateway(self.path, rp_id="approve.test.local",
            origin="https://approve.test.local", owner_id="owner-test",
            signing_key=SECRET, bootstrap_hash=hashlib.sha256(TOKEN.encode()).hexdigest())

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def enroll(self):
        opts = self.db.begin_enrollment(TOKEN, 100)
        with patch("passkey_gateway.verify_registration_response") as mock:
            mock.return_value = SimpleNamespace(credential_id=b"key1",
                credential_public_key=b"publickey", sign_count=0)
            self.db.finish_enrollment(opts["challenge"], {"id": "fake"}, 101)
            self.assertTrue(mock.call_args.kwargs["require_user_verification"])
        return opts

    def test_bootstrap_required(self):
        with self.assertRaises(CeremonyRejected):
            self.db.begin_enrollment("wrong", 100)

    def test_registration_and_second_registration_blocked(self):
        self.enroll()
        with self.assertRaises(CeremonyRejected):
            self.db.begin_enrollment(TOKEN, 102)

    def test_challenge_replay_blocked(self):
        opts = self.enroll()
        with self.assertRaises(CeremonyRejected):
            self.db.finish_enrollment(opts["challenge"], {"id": "fake"}, 103)

    def test_missing_backup_refused_after_passkey_signature(self):
        self.enroll()
        rid = self.db.stage_request(OP, "a"*64, 100)
        opts = self.db.begin_approval(rid, 101)
        with patch("passkey_gateway.verify_authentication_response",
                   return_value=SimpleNamespace(new_sign_count=1)):
            with self.assertRaises(CeremonyRejected):
                self.db.finish_approval(rid, opts["challenge"],
                    {"rawId":"a2V5MQ"}, 102)

    def test_authenticated_approval_one_time(self):
        self.enroll()
        rid = self.db.stage_request(OP, "a"*64, 100)
        opts = self.db.begin_approval(rid, 101)
        with patch("passkey_gateway.verify_authentication_response") as mock:
            mock.return_value = SimpleNamespace(new_sign_count=1)
            nonce = self.db.finish_approval(rid, opts["challenge"],
                {"rawId": "a2V5MQ"}, 102,
                backup_checker=lambda operation, digest: operation == OP and digest == "a"*64)
            self.assertTrue(mock.call_args.kwargs["require_user_verification"])
        self.assertTrue(self.db.db.execute(
            "SELECT COUNT(*) FROM approvals WHERE nonce=?", (nonce,)).fetchone()[0])
        linked = self.db.db.execute(
            "SELECT approved,approval_nonce FROM requests WHERE id=?", (rid,)).fetchone()
        self.assertEqual(linked, (1, nonce))
        with self.assertRaises(CeremonyRejected):
            self.db.finish_approval(rid, opts["challenge"],
                {"rawId": "a2V5MQ"}, 103, backup_checker=lambda *_: True)

    def test_staging_rejects_unspecified_delete_count(self):
        with self.assertRaises(ValueError):
            self.db.stage_request(dict(OP, expected_rows=None), "a"*64, 100)

    def test_staging_rejects_unsupported_action(self):
        with self.assertRaises(ValueError):
            self.db.stage_request(dict(OP, operation="drop"), "a"*64, 100)

    def test_staging_rejects_unscoped_request(self):
        with self.assertRaises(ValueError):
            self.db.stage_request(dict(OP, where={}), "a"*64, 100)

    def test_operation_stable_and_expires(self):
        rid = self.db.stage_request(OP, "b"*64, 100)
        self.assertEqual(self.db.pending(rid, 110), OP)
        with self.assertRaises(CeremonyRejected):
            self.db.pending(rid, 400)

    def test_backup_check_follows_valid_passkey_only(self):
        self.enroll()
        rid = self.db.stage_request(OP, "a"*64, 100)
        opts = self.db.begin_approval(rid, 101)
        steps = []

        def verify(**kwargs):
            steps.append("passkey")
            return SimpleNamespace(new_sign_count=1)

        def backup(operation, digest):
            steps.append("backup")
            self.assertEqual(operation, OP)
            self.assertEqual(digest, "a"*64)
            return False

        with patch("passkey_gateway.verify_authentication_response", side_effect=verify):
            with self.assertRaises(CeremonyRejected):
                self.db.finish_approval(rid, opts["challenge"],
                    {"rawId":"a2V5MQ"}, 102, backup_checker=backup)
        self.assertEqual(steps, ["passkey", "backup"])
        self.assertEqual(
            self.db.db.execute("SELECT COUNT(*) FROM approvals").fetchone()[0], 0)
        steps.clear()
        with patch("passkey_gateway.verify_authentication_response",
                   side_effect=ValueError("invalid WebAuthn signature")):
            with self.assertRaises(CeremonyRejected):
                self.db.finish_approval(rid, opts["challenge"],
                    {"rawId":"a2V5MQ"}, 103, backup_checker=backup)
        self.assertEqual(steps, [])

    def test_staging_global_hourly_quota_and_expiration_cleanup(self):
        for _ in range(20):
            self.db.stage_request(OP, "a"*64, 100)
        with self.assertRaises(CeremonyRejected):
            self.db.stage_request(OP, "a"*64, 100)
        self.assertEqual(
            self.db.db.execute("SELECT COUNT(*) FROM requests").fetchone()[0], 20)
        self.db.stage_request(OP, "a"*64, 3700)
        self.assertEqual(
            self.db.db.execute("SELECT COUNT(*) FROM requests").fetchone()[0], 1)
        other = self.gateway()
        try:
            with self.assertRaises(CeremonyRejected):
                for _ in range(20):
                    other.stage_request(OP, "a"*64, 3700)
        finally:
            other.close()

    def test_staging_daily_quota(self):
        for hour in range(5):
            for _ in range(20):
                self.db.stage_request(OP, "a"*64, hour * 3600 + 100)
        with self.assertRaises(CeremonyRejected):
            self.db.stage_request(OP, "a"*64, 5*3600 + 100)

    def test_staging_rejects_large_operation(self):
        oversized = {**OP, "where":{"id": "x"*9000}}
        with self.assertRaises(ValueError):
            self.db.stage_request(oversized, "a"*64, 100)

    def test_approval_ceremonies_bounded_and_expire(self):
        self.enroll()
        rid = self.db.stage_request(OP, "a"*64, 100)
        for _ in range(3):
            self.db.begin_approval(rid, 101)
        with self.assertRaises(CeremonyRejected):
            self.db.begin_approval(rid, 101)
        self.db.begin_approval(rid, 282)
        self.assertEqual(
            self.db.db.execute(
                "SELECT COUNT(*) FROM ceremonies WHERE kind='approve'"
            ).fetchone()[0], 1)

    def test_invalid_configuration(self):
        with self.assertRaises(ValueError):
            PasskeyGateway(self.path, rp_id="approve.test.local",
                origin="http://approve.test.local", owner_id="x",
                signing_key=SECRET, bootstrap_hash="a"*64)

if __name__ == "__main__":
    unittest.main()
