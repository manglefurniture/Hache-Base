"""Regression coverage for no-write owner WebAuthn passkey proof."""
import hashlib
import os
import pathlib
import sqlite3
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from passkey_gateway import PasskeyGateway, CeremonyRejected
from approval_web import create_app

SECRET = b"passkey-check-test-secret-at-least-thirtytwo-bytes"
ORIGIN = "https://approve.test.local"
TOKEN = "out-of-band-test-token"


class OwnerPasskeyCheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "proof.sqlite")
        self.g = PasskeyGateway(self.path, rp_id="approve.test.local",
                                origin=ORIGIN, owner_id="test-owner",
                                signing_key=SECRET,
                                bootstrap_hash=hashlib.sha256(TOKEN.encode()).hexdigest())

    def tearDown(self):
        self.g.close()
        self.tmp.cleanup()

    def register_fake_credential(self):
        self.g.db.execute("INSERT INTO passkeys VALUES (?,?,?)",
                          (b"test-passkey", b"test-public-key", 0))

    def test_proof_requires_registered_owner(self):
        with self.assertRaises(CeremonyRejected):
            self.g.begin_passkey_check(100)

    def test_proof_does_not_issue_grants_or_create_sql_requests(self):
        self.register_fake_credential()
        options = self.g.begin_passkey_check(100)
        with patch("passkey_gateway.verify_authentication_response",
                   return_value=SimpleNamespace(new_sign_count=1)) as verified:
            self.assertTrue(self.g.finish_passkey_check(options["challenge"],
                {"rawId": "dGVzdC1wYXNza2V5"}, 101))
            self.assertTrue(verified.call_args.kwargs["require_user_verification"])
            self.assertEqual(verified.call_args.kwargs["expected_origin"], ORIGIN)
            self.assertEqual(verified.call_args.kwargs["expected_rp_id"], "approve.test.local")
        for table in ("approvals", "requests"):
            count = self.g.db.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]
            self.assertEqual(count, 0)
        self.assertEqual(self.g.db.execute(
            "SELECT sign_count FROM passkeys").fetchone()[0], 1)
        with self.assertRaises(CeremonyRejected):
            self.g.finish_passkey_check(options["challenge"],
                {"rawId": "dGVzdC1wYXNza2V5"}, 102)

    def test_invalid_assertion_is_rejected_and_keeps_counter(self):
        self.register_fake_credential()
        options = self.g.begin_passkey_check(100)
        with patch("passkey_gateway.verify_authentication_response",
                   side_effect=ValueError("invalid")):
            with self.assertRaises(CeremonyRejected):
                self.g.finish_passkey_check(options["challenge"],
                    {"rawId": "dGVzdC1wYXNza2V5"}, 101)
        self.assertEqual(self.g.db.execute(
            "SELECT sign_count FROM passkeys").fetchone()[0], 0)
        self.assertEqual(self.g.db.execute(
            "SELECT COUNT(*) FROM approvals").fetchone()[0], 0)

    def test_expiration_and_global_limit(self):
        self.register_fake_credential()
        challenge = self.g.begin_passkey_check(100)
        with self.assertRaises(CeremonyRejected):
            self.g.finish_passkey_check(challenge["challenge"],
                {"rawId": "dGVzdC1wYXNza2V5"}, 221)
        self.g.begin_passkey_check(221)
        self.g.begin_passkey_check(222)
        self.g.begin_passkey_check(223)
        with self.assertRaises(CeremonyRejected):
            self.g.begin_passkey_check(224)
        self.g.begin_passkey_check(344)
        self.g.begin_passkey_check(345)
        with self.assertRaises(CeremonyRejected):
            self.g.begin_passkey_check(346)
        # Quota remains durable if a new gateway opens the same file.
        other = PasskeyGateway(self.path, rp_id="approve.test.local",
                                origin=ORIGIN, owner_id="test-owner",
                                signing_key=SECRET,
                                bootstrap_hash=hashlib.sha256(TOKEN.encode()).hexdigest())
        try:
            with self.assertRaises(CeremonyRejected):
                other.begin_passkey_check(347)
        finally:
            other.close()


class OwnerPasskeyWebTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config = {
            "DB_PATH": os.path.join(self.tmp.name, "proof.sqlite"),
            "RP_ID": "approve.test.local",
            "ORIGIN": ORIGIN,
            "OWNER_ID": "owner",
            "SIGN_KEY_HEX": "a1" * 32,
            "BOOTSTRAP_HASH": hashlib.sha256(b"boot").hexdigest(),
            "AGENT_TOKEN": "secret-agent-token-more-than-thirtytwo-characters",
        }
        self.app = create_app(self.config)
        self.client = self.app.test_client()
        # Initialize the private schema as the trusted service would on start.
        gateway = PasskeyGateway(
            self.config["DB_PATH"], rp_id=self.config["RP_ID"],
            origin=self.config["ORIGIN"], owner_id=self.config["OWNER_ID"],
            signing_key=bytes.fromhex(self.config["SIGN_KEY_HEX"]),
            bootstrap_hash=self.config["BOOTSTRAP_HASH"])
        gateway.close()

    def tearDown(self):
        self.tmp.cleanup()

    def req(self, method, route, **kwargs):
        return self.client.open(route, method=method, base_url=ORIGIN, **kwargs)

    def test_proof_page_and_post_origin_required(self):
        response = self.req("GET", "/verify-passkey")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"No aprueba operaciones", response.data)
        self.assertEqual(self.req("POST", "/api/passkey-check/start",
                                 json={}, headers={"Origin":"https://attacker.test"}).status_code, 403)
        with sqlite3.connect(self.config["DB_PATH"]) as db:
            db.execute("INSERT INTO passkeys VALUES (?,?,0)", (b"test-passkey", b"public"))
        opts = self.req("POST", "/api/passkey-check/start", json={},
                       headers={"Origin":ORIGIN})
        self.assertEqual(opts.status_code, 200, opts.text)
        with patch("passkey_gateway.verify_authentication_response",
                   return_value=SimpleNamespace(new_sign_count=2)):
            done = self.req("POST", "/api/passkey-check/finish",
                            json={"challenge":opts.json["challenge"],
                                  "credential":{"rawId":"dGVzdC1wYXNza2V5"}},
                            headers={"Origin":ORIGIN})
        self.assertEqual(done.status_code, 200)
        self.assertEqual(done.json, {"status":"verified","grants_issued":0})
        with sqlite3.connect(self.config["DB_PATH"]) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM approvals").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM requests").fetchone()[0], 0)

    def test_no_unregistered_passkey_and_no_agent_bypass(self):
        response = self.req("POST", "/api/passkey-check/start", json={},
                            headers={"Origin":ORIGIN})
        self.assertEqual(response.status_code, 403)
        response = self.req("POST", "/api/agent/stage", json={},
                            headers={"Origin":ORIGIN})
        self.assertEqual(response.status_code, 401)


class ProofNginxTests(unittest.TestCase):
    def test_public_routes_are_only_passkey_proof(self):
        src = (pathlib.Path(__file__).resolve().parent / "deploy" / "nginx" /
               "aprobaciones-passkey-check-only.conf.example").read_text()
        for path in ("/verify-passkey", "/static/passkey_check.js",
                     "/static/approval.css", "/api/passkey-check/start",
                     "/api/passkey-check/finish"):
            self.assertIn("location = " + path + " {", src)
        self.assertEqual(src.count("proxy_pass http://127.0.0.1:8173;"), 5)
        self.assertNotIn("location = /api/enroll/start", src)
        self.assertNotIn("location = /api/approve/start", src)
        self.assertNotIn("location = /api/agent/stage", src)
        self.assertIn('return 503 "Hache SQL Guard:', src)
        self.assertIn("MUST be DNS-only", src)
        self.assertEqual(src.count("limit_except POST { deny all; }"), 2)


if __name__ == "__main__":
    unittest.main()
