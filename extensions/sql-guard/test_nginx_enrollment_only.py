"""Regression checks for the restricted public WebAuthn enrollment proxy."""
import pathlib
import re
import unittest

CONF = (pathlib.Path(__file__).resolve().parent / "deploy" / "nginx" /
        "aprobaciones-enrollment-only.conf.example")


class EnrollmentOnlyNginxContractTests(unittest.TestCase):
    def setUp(self):
        self.text = CONF.read_text(encoding="utf-8")

    def test_exact_public_route_allowlist(self):
        allowed = re.findall(r"^\s*location\s*=\s*(/\S+)\s*\{", self.text, re.M)
        self.assertCountEqual(allowed, [
            "/enroll", "/static/approval.js", "/static/approval.css",
            "/api/enroll/start", "/api/enroll/finish",
        ])
        self.assertNotIn("location /api/", self.text)
        self.assertNotIn("location ^~ /api/", self.text)
        self.assertIn('return 503 "Hache SQL Guard: enrollment-only staging', self.text)

    def test_local_only_tls_and_origin(self):
        self.assertIn("server_name aprobaciones.hacheinteractive.com", self.text)
        self.assertIn("listen 443 ssl;", self.text)
        self.assertIn("listen [::]:443 ssl;", self.text)
        self.assertIn("proxy_pass http://127.0.0.1:8173;", self.text)
        self.assertNotIn("proxy_pass http://0.0.0.0", self.text)
        self.assertIn("proxy_set_header Host $host;", self.text)
        self.assertIn("proxy_set_header X-Forwarded-Proto https;", self.text)
        self.assertIn("ssl_protocols TLSv1.2 TLSv1.3;", self.text)

    def test_enrollment_only_post_and_throttle(self):
        self.assertEqual(self.text.count("limit_except POST { deny all; }"), 2)
        self.assertEqual(self.text.count("limit_except GET { deny all; }"), 3)
        self.assertEqual(self.text.count("limit_req zone=sqlguard_enroll_api"), 2)
        self.assertIn("limit_req_zone $binary_remote_addr", self.text)
        self.assertIn('MUST be DNS-only', self.text)
        self.assertIn("Cloudflare HTTP proxy", self.text)
        self.assertIn("limit_req_status 429", self.text)
        self.assertIn("client_max_body_size 16k", self.text)

    def test_no_other_proxy_routes_or_agent_token(self):
        self.assertEqual(self.text.count("proxy_pass http://127.0.0.1:8173;"), 5)
        self.assertNotIn("SQLGUARD_AGENT_TOKEN", self.text)
        self.assertNotIn("proxy_set_header Authorization", self.text)
        self.assertIn("location ^~ /.well-known/acme-challenge/", self.text)
        self.assertIn('add_header Cache-Control "no-store" always;', self.text)


if __name__ == "__main__":
    unittest.main()
