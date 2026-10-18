"""Read-only staging diagnostic contract tests; no VPS/root required."""
import os
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent
SCRIPT = ROOT / "deploy" / "preflight-staging.sh"


class StagingPreflightTests(unittest.TestCase):
    def test_shell_syntax(self):
        subprocess.run(["bash", "-n", str(SCRIPT)], check=True)

    def test_help_never_queries_server(self):
        p = subprocess.run(["bash", str(SCRIPT), "--help"],
                           capture_output=True, text=True, check=True, timeout=5)
        self.assertIn("--require-staged", p.stdout)
        self.assertNotIn("SQL Guard staging inspection", p.stdout)

    def test_invalid_arguments_fail_closed(self):
        p = subprocess.run(["bash", str(SCRIPT), "--something-else"],
                           capture_output=True, text=True, timeout=5)
        self.assertEqual(p.returncode, 2)

    def test_shared_sqlite_units_require_group_umask(self):
        deploy = ROOT / "deploy"
        for unit in ("sqlguard-approval.service.example",
                     "sqlguard-runner.service.example"):
            body = (deploy / unit).read_text()
            self.assertIn("UMask=0007", body)
            self.assertNotIn("UMask=0077", body)

    def test_rejects_cross_group_membership_in_report(self):
        # Only discovery tools are mocked; the script never writes VPS state.
        with tempfile.TemporaryDirectory() as folder:
            mock = pathlib.Path(folder)
            executables = {
                "getent": "#!/bin/bash\nexit 0\n",
                "systemctl": "#!/bin/bash\nexit 0\n",
                "curl": "#!/bin/bash\nprintf '503/0'\n",
                "id": """#!/bin/bash
[[ "$1" == "-nG" ]] || exit 1
case "$2" in
  gpt-agent) echo 'gpt-agent sqlguard-callers sqlguard-store';;
  sqlguard-approval) echo 'sqlguard-store';;
  sqlguard-runner) echo 'sqlguard-runner sqlguard-store sqlguard-callers';;
  *) exit 1;;
esac
""",
            }
            for name, content in executables.items():
                p = mock / name
                p.write_text(content)
                p.chmod(0o755)
            env = {**os.environ, "PATH": folder + os.pathsep + os.environ["PATH"]}
            result = subprocess.run(
                ["bash", str(SCRIPT), "--report"], env=env,
                capture_output=True, text=True, timeout=10, check=True)
            self.assertRegex(result.stdout, r"(?m)^GPT excluded from store\s+MISSING$")
            self.assertRegex(result.stdout, r"(?m)^Runner in socket group\s+OK$")

    def test_socket_dir_is_part_of_readiness_gate(self):
        source = SCRIPT.read_text()
        self.assertIn("dir_owned /run/sqlguard 'root:sqlguard-runner:771'", source)

    def test_no_mutation_commands_in_inspection_source(self):
        src = SCRIPT.read_text()
        # Prevent accidentally extending the diagnostic with installers.
        for forbidden in ("sudo ", "systemctl start ", "systemctl enable ",
                          "useradd ", "usermod ", "groupadd ", "chmod ",
                          "chown ", "mariadb -e ", "CREATE USER ", "GRANT ",
                          "REVOKE ", "git clone ", "pip install ", "curl | bash"):
            self.assertNotIn(forbidden, src)


if __name__ == "__main__":
    unittest.main()
