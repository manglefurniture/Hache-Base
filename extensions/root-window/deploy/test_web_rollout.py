import pathlib
import unittest

HERE=pathlib.Path(__file__).resolve().parent
VHOST=HERE/"nginx/aprobaciones-root-window-only.conf.example"
INSTALLER=HERE/"install-sqlguard-web.sh"

class WebRolloutPolicyTests(unittest.TestCase):
    def test_exact_allowlisted_routes(self):
        s=VHOST.read_text()
        allowed={"/root-window","/static/root_window.js","/static/approval.css",
                 "/api/root-window/status","/api/root-window/start","/api/root-window/finish"}
        import re
        locations=set(re.findall(r'location = (/[^ ]+) \{',s))
        self.assertEqual(locations,allowed)
        self.assertEqual(s.count("proxy_pass http://127.0.0.1:8173;"),6)
        self.assertIn('return 503 "Hache SQL Guard:',s)
        self.assertNotIn("location = /api/agent",s)
        self.assertNotIn("location = /enroll",s)
        self.assertNotIn("location = /approve",s)
        self.assertNotIn("location = /verify-passkey",s)
        for route in allowed:
            start=s.index("location = "+route+" {")
            segment=s[start:s.index("\n    }",start)]
            self.assertIn("limit_except ",segment)
            if route in {"/api/root-window/start","/api/root-window/finish"}:
                self.assertIn("limit_except POST { deny all; }",segment)
                self.assertIn("limit_req zone=",segment)
    def test_installer_requires_pinned_repo_and_validated_passkey(self):
        s=INSTALLER.read_text()
        for marker in ("COMMIT_MISMATCH","DIRTY_SOURCE","UNMERGED_SOURCE",
                       "PASSKEY_COUNT_NOT_ONE","SYSTEMD_SMOKE_FAILED",
                       "nginx -t","SQLGUARD_ROOT_WINDOW_OWNER_AUTH_SHA256",
                       "WINDOW_SOCKET_FAILURE"):
            self.assertIn(marker,s)
        self.assertNotIn("chmod 777",s)
        self.assertNotIn("NOPASSWD",s)
        self.assertIn('"git","-C",repo,"archive"',s)
        self.assertIn('UNSAFE_TRACKED_ENTRY',s)
        self.assertNotIn('cp -a "$SRC"',s)
        self.assertIn('for attempt in {1..30}',s)
        self.assertIn('READY_PUBLIC=1',s)
        self.assertIn('--resolve aprobaciones.hacheinteractive.com:443:127.0.0.1',s)
        self.assertIn('PUBLIC_AUTH_FAILURE local=',s)
        self.assertIn('"$blocked_public" == 503',s)
if __name__=="__main__":unittest.main()
