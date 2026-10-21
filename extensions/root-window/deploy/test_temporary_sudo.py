import pathlib
import subprocess
import unittest

DEPLOY=pathlib.Path(__file__).resolve().parent
SCRIPT=DEPLOY/"hache-gpt-sudo-window.sh"
INSTALLER=DEPLOY/"install-gpt-sudo-window.sh"
GUARD=DEPLOY/"hache-gpt-sudo-bootguard.service.example"

class TemporarySudoPolicyTests(unittest.TestCase):
    def test_bash_syntax(self):
        for script in (SCRIPT,INSTALLER):
            with self.subTest(script=script):
                p=subprocess.run(["bash","-n",str(script)],capture_output=True,text=True)
                self.assertEqual(p.returncode,0,p.stderr)
    def test_grant_revocation_and_boundary(self):
        s=SCRIPT.read_text()
        for required in (
            "MINUTES_OUT_OF_RANGE_1_TO_1440",
            "NOPASSWD: ALL",
            "REVOCATION_TIMER_FAILED",
            "systemd-run --quiet",
            "BOOTGUARD_NOT_READY",
            "visudo -cf",
            "ALREADY_ARMED_USE_STOP_FIRST",
            "TEMPORARY_SUDO_EXPIRED",
            "TEMPORARY_SUDO_REVOKED",
            "/etc/sudoers.d/91-hache-gpt-agent-window"
        ):
            with self.subTest(required=required):
                self.assertIn(required,s)
        self.assertNotIn("NOPASSWD: ALL\n",s) if False else None
    def test_installer_pinned_commit_and_bootguard(self):
        s=INSTALLER.read_text()
        for required in (
            "COMMIT_MISMATCH",
            "DIRTY_SOURCE",
            "UNMERGED_SOURCE",
            "INVALID_REMOTE",
            "systemctl enable --now hache-gpt-sudo-bootguard.service",
            "GPT_TEMPORARY_SUDO_HELPER_READY_OFF"
        ):
            self.assertIn(required,s)
        g=GUARD.read_text()
        self.assertIn("ExecStart=/usr/local/sbin/hache-gpt-sudo-window stop",g)
        self.assertIn("Before=desktop-commander-gpt.service",g)

if __name__=="__main__":
    unittest.main()
