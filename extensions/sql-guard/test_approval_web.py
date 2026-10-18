import hashlib
import os
import tempfile
import unittest

from approval_web import create_app

TOKEN = "a-long-agent-secret-token-at-least-32-characters"
OP = {"database":"sandbox","table":"items","operation":"delete","where":{"id":1},"values":{},"expected_rows":1,"expected_primary_keys":[1]}


class WebTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config = {
            "DB_PATH": os.path.join(self.tmp.name, "gateway.sqlite"),
            "RP_ID": "approve.test.local",
            "ORIGIN": "https://approve.test.local",
            "OWNER_ID": "owner-test",
            "SIGN_KEY_HEX": "a1"*32,
            "BOOTSTRAP_HASH": hashlib.sha256(b"boot").hexdigest(),
            "AGENT_TOKEN": TOKEN,
        }
        self.app = create_app(self.config)
        self.client = self.app.test_client()
        self.origin = {"Origin": "https://approve.test.local"}
        self.agent = {"Authorization": "Bearer " + TOKEN}

    def tearDown(self):
        self.tmp.cleanup()

    def req(self, method, url, **kwargs):
        return self.client.open(url, method=method,
            base_url="https://approve.test.local", **kwargs)

    def stage(self):
        resp = self.req("POST", "/api/agent/stage",
            json={"operation": OP, "backup_digest": "a"*64},
            headers=self.agent)
        self.assertEqual(resp.status_code, 201, resp.text)
        return resp.json["request_id"]

    def test_agent_token_required(self):
        self.assertEqual(self.req("POST", "/api/agent/stage",
            json={"operation":OP,"backup_digest":"a"*64}).status_code, 401)
        rid = self.stage()
        self.assertEqual(self.req("GET", "/api/agent/status/"+rid).status_code, 401)
        self.assertEqual(self.req("GET", "/api/agent/status/"+rid,
            headers=self.agent).json["status"], "pending")

    def test_wrong_origin_rejected(self):
        self.assertEqual(self.req("POST", "/api/enroll/start",
            headers={"Origin":"https://evil.test"},
            json={"bootstrap_token":"boot"}).status_code, 403)

    def test_request_page_and_previews(self):
        rid = self.stage()
        response = self.req("GET", "/approve/"+rid)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Hache SQL Guard", response.data)
        self.assertEqual(response.headers["Referrer-Policy"], "no-referrer")
        self.assertEqual(self.req("GET", "/api/pending/"+rid).json, OP)

    def test_request_not_found(self):
        self.assertEqual(self.req("GET", "/approve/"+"q"*24).status_code, 403)

    def test_fails_closed_without_backup_verifier(self):
        rid = self.stage()
        resp = self.req("POST", "/api/approve/finish", headers=self.origin,
            json={"request_id":rid, "challenge":"abc",
                  "credential":{"rawId":"abc"}})
        self.assertEqual(resp.status_code, 403)

    def test_unauthed_enroll_refused(self):
        resp = self.req("POST", "/api/enroll/start", headers=self.origin,
            json={"bootstrap_token":"invalid"})
        self.assertEqual(resp.status_code, 403)

    def test_invalid_config_fails(self):
        with self.assertRaises(RuntimeError):
            create_app({**self.config, "AGENT_TOKEN": "short"})


if __name__ == "__main__":
    unittest.main()
