"""Unit contract for low-memory, isolated SQL Guard approval staging."""
import pathlib
import unittest

UNIT = pathlib.Path(__file__).resolve().parent / "deploy" / "sqlguard-approval.service.example"


class ApprovalUnitStagingTests(unittest.TestCase):
    def test_one_worker_local_only_and_memory_bounded(self):
        content = UNIT.read_text()
        self.assertIn("--workers 1 --bind 127.0.0.1:8173", content)
        self.assertNotIn("--workers 2", content)
        self.assertIn("MemoryHigh=160M", content)
        self.assertIn("MemoryMax=224M", content)
        self.assertIn("TasksMax=48", content)

    def test_isolation_and_explicit_no_auto_enable(self):
        content = UNIT.read_text()
        for item in (
            "User=sqlguard-approval", "Group=sqlguard-store",
            "EnvironmentFile=/etc/sqlguard/approval.env",
            "UMask=0007", "ProtectSystem=strict",
            "NoNewPrivileges=yes", "ReadWritePaths=/var/lib/sqlguard",
        ):
            self.assertIn(item, content)
        self.assertNotIn("ExecStartPre=", content)
        self.assertNotIn("User=root", content)
        self.assertNotIn("--bind 0.0.0.0", content)


if __name__ == "__main__":
    unittest.main()
