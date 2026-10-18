"""Safety contract for the root-operated SQL Guard staging bootstrap."""
import pathlib
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parent
DEPLOY = ROOT / "deploy"
SCRIPT = DEPLOY / "bootstrap-staging-root.sh"
TMPFILES = DEPLOY / "sqlguard-tmpfiles.conf.example"

class BootstrapStagingTests(unittest.TestCase):
    def test_shell_syntax(self):
        subprocess.run(["bash", "-n", str(SCRIPT)], check=True)

    def test_bad_arguments_rejected(self):
        p = subprocess.run(["bash", str(SCRIPT), "--bogus"],
                           capture_output=True, text=True, timeout=5)
        self.assertEqual(p.returncode, 2)

    def test_default_mode_is_read_only(self):
        src = SCRIPT.read_text()
        self.assertIn('mode="--check"', src)
        self.assertIn('echo "READ_ONLY_OK (no changes)"', src)
        self.assertIn('[[ "$(id -u)" == 0 ]]', src)
        self.assertIn('if [[ "$mode" == "--check" ]]; then', src)

    def test_no_unrestricted_privilege_grants(self):
        src = SCRIPT.read_text()
        self.assertIn("usermod -a -G sqlguard-callers gpt-agent", src)
        self.assertIn("member gpt-agent sqlguard-store", src)
        self.assertIn("account_check sqlguard-approval", src)
        self.assertIn("account_check sqlguard-runner", src)
        self.assertNotIn("usermod -a -G sudo", src)
        self.assertNotIn("usermod -a -G root", src)
        self.assertNotIn("NOPASSWD:", src)
        self.assertNotIn("systemctl restart ", src)
        self.assertNotIn("systemctl enable ", src)
        self.assertNotIn("mariadb -e ", src)
        self.assertNotIn("curl | bash", src)

    def test_root_private_paths_and_tmpfiles(self):
        src = SCRIPT.read_text()
        self.assertEqual(TMPFILES.read_text().strip(),
                         "d /run/sqlguard 0771 root sqlguard-runner -")
        self.assertIn("systemd-tmpfiles --create", src)
        self.assertIn("ensure_directory /var/lib/sqlguard root sqlguard-store 2770", src)
        self.assertIn("ensure_directory /var/lib/sqlguard-trusted root sqlguard-store 750", src)
        self.assertIn("ensure_directory /etc/sqlguard root root 700", src)

if __name__ == "__main__":
    unittest.main()
