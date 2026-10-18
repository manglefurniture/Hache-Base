import hashlib
import hmac
import unittest

from approval import Approval, _message, canonical_operation, verify_approval

SECRET = b"a-test-secret-that-is-at-least-32-bytes-long"
OP = {"database": "sandbox", "table": "items", "operation": "delete",
      "where": {"status": "expired"}, "values": {}}


def issue(operation=OP, *, expires_at=200, nonce="once", backup="a" * 64):
    a = Approval(canonical_operation(operation), "human-123", expires_at, nonce, backup, "")
    return Approval(a.operation_digest, a.approver_id, a.expires_at, a.nonce,
                    a.backup_digest, hmac.new(SECRET, _message(a), hashlib.sha256).hexdigest())


class ApprovalTests(unittest.TestCase):
    def test_valid(self):
        self.assertTrue(verify_approval(issue(), OP, SECRET, set(), now=100))

    def test_replay_refused(self):
        self.assertFalse(verify_approval(issue(), OP, SECRET, {"once"}, now=100))

    def test_expired(self):
        self.assertFalse(verify_approval(issue(), OP, SECRET, set(), now=200))

    def test_too_long(self):
        self.assertFalse(verify_approval(issue(expires_at=1000), OP, SECRET, set(), now=100))

    def test_modified_operation(self):
        changed = dict(OP, where={"status": "active"})
        self.assertFalse(verify_approval(issue(), changed, SECRET, set(), now=100))

    def test_wrong_key(self):
        self.assertFalse(verify_approval(issue(), OP, b"another-secret-with-32-bytes-minimum", set(), now=100))

    def test_missing_backup(self):
        self.assertFalse(verify_approval(issue(backup=""), OP, SECRET, set(), now=100))

    def test_unexpected_field(self):
        self.assertFalse(verify_approval(issue(), dict(OP, override=True), SECRET, set(), now=100))


if __name__ == "__main__":
    unittest.main()
