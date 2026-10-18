"""Contract checks for root-only approval-store preparation."""
import pathlib
import subprocess
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parent / "deploy" / "prepare-approval-store.sh"


class ApprovalStorePreparationTests(unittest.TestCase):
    def test_shell_syntax(self):
        subprocess.run(["bash", "-n", str(SCRIPT)], check=True)

    def test_default_is_check_only(self):
        content = SCRIPT.read_text()
        self.assertIn('mode="--check"', content)
        self.assertIn('[[ "$(id -u)" == 0 ]]', content)
        self.assertIn('CHECK_ONLY: no changes made', content)

    def test_secrets_never_printed_or_disclosed_to_agent(self):
        content = SCRIPT.read_text()
        for forbidden in ("cat /etc/sqlguard/approval.env", "cat /root/sqlguard-enrollment-token",
                          "source /etc/sqlguard/approval.env", "chmod 777",
                          "systemctl start ", "systemctl enable ", "mariadb -e ",
                          "usermod -a", "sudoers", "NOPASSWD:"):
            self.assertNotIn(forbidden, content)
        self.assertIn('owner_mode /etc/sqlguard/approval.env "0:0:600"', content)
        self.assertIn('owner_mode /root/sqlguard-enrollment-token "0:0:600"', content)

    def test_user_isolation_and_schema_validation(self):
        content = SCRIPT.read_text()
        self.assertIn('runuser -u sqlguard-approval -g sqlguard-store', content)
        self.assertIn('runuser -u sqlguard-runner -g sqlguard-runner', content)
        self.assertIn('runuser -u gpt-agent --', content)
        self.assertIn('required = {"passkeys", "requests", "ceremonies", "approvals", "stage_budget"}', content)
        self.assertIn('owner_mode "$db"', content)

    def test_unknown_option_fails(self):
        result = subprocess.run(["bash", str(SCRIPT), "--unknown"],
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
