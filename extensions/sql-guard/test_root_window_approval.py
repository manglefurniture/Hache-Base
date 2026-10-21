import hashlib
import hmac
import json
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from passkey_gateway import PasskeyGateway,CeremonyRejected
from approval_web import create_app

KEY=b"root-window-test-secret-32-bytes"
ORIGIN="https://approve.test.local"
class OwnerWindowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=os.path.join(self.temp.name,"approvals.sqlite")
        self.g=PasskeyGateway(self.path,rp_id="approve.test.local",origin=ORIGIN,owner_id="owner",
                              signing_key=b"test-sqlguard-signing-key-more-than-32",
                              bootstrap_hash=hashlib.sha256(b"bootstrap").hexdigest())
        self.g.db.execute("INSERT INTO passkeys VALUES (?,?,0)",(b"test-passkey",b"public"))
    def tearDown(self):
        self.g.close();self.temp.cleanup()
    def test_enable_disable_with_passkey_and_no_sql_grant(self):
        for action in ("enable","disable"):
            opts=self.g.begin_root_window(action,100)
            with patch("passkey_gateway.verify_authentication_response",return_value=SimpleNamespace(new_sign_count=1)) as called:
                ticket=self.g.finish_root_window(action,opts["challenge"],{"rawId":"dGVzdC1wYXNza2V5"},101,window_key=KEY)
            self.assertTrue(called.call_args.kwargs["require_user_verification"])
            self.assertEqual(called.call_args.kwargs["expected_origin"],ORIGIN)
            self.assertEqual(ticket["payload"]["action"],action)
            self.assertEqual(ticket["signature"],hmac.new(KEY,json.dumps(ticket["payload"],sort_keys=True,separators=(",",":"),ensure_ascii=True).encode(),hashlib.sha256).hexdigest())
            with self.assertRaises(CeremonyRejected):
                self.g.finish_root_window(action,opts["challenge"],{"rawId":"dGVzdC1wYXNza2V5"},101,window_key=KEY)
        self.assertEqual(self.g.db.execute("SELECT COUNT(*) FROM approvals").fetchone()[0],0)
        self.assertEqual(self.g.db.execute("SELECT COUNT(*) FROM requests").fetchone()[0],0)
    def test_cross_action_and_expired(self):
        opts=self.g.begin_root_window("enable",100)
        with self.assertRaises(CeremonyRejected):
            self.g.finish_root_window("disable",opts["challenge"],{"rawId":"dGVzdC1wYXNza2V5"},101,window_key=KEY)
        with self.assertRaises(CeremonyRejected):
            self.g.finish_root_window("enable",opts["challenge"],{"rawId":"dGVzdC1wYXNza2V5"},221,window_key=KEY)
    def test_owner_auth_required_before_web_auth_quota(self):
        password="R"*48
        config={"DB_PATH":self.path,"RP_ID":"approve.test.local","ORIGIN":ORIGIN,
            "OWNER_ID":"owner","SIGN_KEY_HEX":"a1"*32,
            "BOOTSTRAP_HASH":hashlib.sha256(b"boot").hexdigest(),
            "AGENT_TOKEN":"agent-secret-token-more-than-thirty-two",
            "ROOT_WINDOW_OWNER_AUTH_SHA256":hashlib.sha256(password.encode()).hexdigest(),
            "ROOT_WINDOW_KEY_HEX":"a1"*32,
            "ROOT_WINDOW_SOCKET":"/run/hache-root-window/admin.sock"}
        c=create_app(config).test_client()
        req={"action":"enable"}
        noauth=c.post("/api/root-window/start",base_url=ORIGIN,json=req,headers={"Origin":ORIGIN})
        self.assertEqual(noauth.status_code,401)
        self.assertIn("Basic",noauth.headers["WWW-Authenticate"])
        self.assertEqual(self.g.db.execute("SELECT COUNT(*) FROM ceremonies").fetchone()[0],0)
        bad=c.post("/api/root-window/start",base_url=ORIGIN,json=req,headers={"Origin":ORIGIN},
            auth=("owner","incorrect"+"x"*32))
        self.assertEqual(bad.status_code,401)
        self.assertEqual(self.g.db.execute("SELECT COUNT(*) FROM ceremonies").fetchone()[0],0)
        good=c.post("/api/root-window/start",base_url=ORIGIN,json=req,headers={"Origin":ORIGIN},
            auth=("owner",password))
        self.assertEqual(good.status_code,200)
        self.assertEqual(self.g.db.execute("SELECT COUNT(*) FROM ceremonies").fetchone()[0],1)
        denied=c.get("/root-window",base_url=ORIGIN)
        self.assertEqual(denied.status_code,401)
        ok=c.get("/root-window",base_url=ORIGIN,auth=("owner",password))
        self.assertEqual(ok.status_code,200)
        self.assertIn(b"Activar 10 minutos",ok.data)

    def test_http_off_by_default_and_origin(self):
        config={"DB_PATH":self.path,"RP_ID":"approve.test.local","ORIGIN":ORIGIN,
            "OWNER_ID":"owner","SIGN_KEY_HEX":"a1"*32,
            "BOOTSTRAP_HASH":hashlib.sha256(b"boot").hexdigest(),
            "AGENT_TOKEN":"agent-secret-token-more-than-thirty-two"}
        c=create_app(config).test_client()
        self.assertEqual(c.get("/root-window",base_url=ORIGIN).status_code,503)
        self.assertEqual(c.get("/api/root-window/status",base_url=ORIGIN).status_code,503)
        self.assertEqual(c.post("/api/root-window/start",base_url=ORIGIN,json={"action":"enable"},
            headers={"Origin":"https://evil.example"}).status_code,403)
        self.assertEqual(c.post("/api/root-window/start",base_url=ORIGIN,json={"action":"enable"},
            headers={"Origin":ORIGIN}).status_code,503)
if __name__=="__main__":unittest.main()
