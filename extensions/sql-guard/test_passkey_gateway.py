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
OP = {"database":"sandbox","table":"items","operation":"delete","where":{"id":1},"values":{},"expected_rows":1}


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

    def test_missing_backup_refused_before_signature(self):
        self.enroll()
        rid = self.db.stage_request(OP, "a"*64, 100)
        opts = self.db.begin_approval(rid, 101)
        with self.assertRaises(CeremonyRejected):
            self.db.finish_approval(rid, opts["challenge"], {"rawId": "a2V5MQ"}, 102)

    def test_authenticated_approval_one_time(self):
        self.enroll()
        rid = self.db.stage_request(OP, "a"*64, 100)
        opts = self.db.begin_approval(rid, 101)
        with patch("passkey_gateway.verify_authentication_response") as mock:
            mock.return_value = SimpleNamespace(new_sign_count=1)
            nonce = self.db.finish_approval(rid, opts["challenge"],
                {"rawId": "a2V5MQ"}, 102, backup_is_verified=True)
            self.assertTrue(mock.call_args.kwargs["require_user_verification"])
        self.assertTrue(self.db.db.execute(
            "SELECT COUNT(*) FROM approvals WHERE nonce=?", (nonce,)).fetchone()[0])
        with self.assertRaises(CeremonyRejected):
            self.db.finish_approval(rid, opts["challenge"],
                {"rawId": "a2V5MQ"}, 103, backup_is_verified=True)

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

    def test_invalid_configuration(self):
        with self.assertRaises(ValueError):
            PasskeyGateway(self.path, rp_id="approve.test.local",
                origin="http://approve.test.local", owner_id="x",
                signing_key=SECRET, bootstrap_hash="a"*64)

if __name__ == "__main__":
    unittest.main()
