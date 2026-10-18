import os
import tempfile
import unittest

from approval_issuer import VerifiedHuman, issue_approval
from approval_store import ApprovalStore

SECRET = b"a-secret-key-at-least-32-characters"
OP = {"database": "sandbox", "table": "items", "operation": "delete", "where": {"status": "old"}, "values": {}}


class IssuerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = ApprovalStore(os.path.join(self.tmp.name, "approvals.sqlite"))

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def issue(self, human):
        return issue_approval(self.store, SECRET, OP, principal=human,
            expected_owner_id="owner-123", backup_digest="a" * 64, now=1000)

    def test_owner_recent_auth(self):
        approval = self.issue(VerifiedHuman("owner-123", 999))
        self.assertTrue(self.store.consume(approval.nonce, OP, SECRET, now=1001))
        self.assertFalse(self.store.consume(approval.nonce, OP, SECRET, now=1001))

    def test_other_user_cannot_approve(self):
        with self.assertRaises(PermissionError):
            self.issue(VerifiedHuman("someone-else", 999))

    def test_stale_authentication_refused(self):
        with self.assertRaises(PermissionError):
            self.issue(VerifiedHuman("owner-123", 500))

    def test_missing_backup_refused(self):
        with self.assertRaises(PermissionError):
            issue_approval(self.store, SECRET, OP, principal=VerifiedHuman("owner-123", 999),
                expected_owner_id="owner-123", backup_digest="", now=1000)


if __name__ == "__main__":
    unittest.main()
