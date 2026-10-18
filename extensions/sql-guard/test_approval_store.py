import hashlib
import hmac
import os
import tempfile
import unittest

from approval import Approval, canonical_operation, _message
from approval_store import ApprovalStore

SECRET = b"independent-gateway-test-secret-32bytes"
OP = {"database": "sandbox", "table": "items", "operation": "delete",
      "where": {"status": "old"}, "values": {}}


def signed(nonce, *, exp=120):
    x = Approval(canonical_operation(OP), "human-123", exp, nonce, "a" * 64, "")
    return Approval(x.operation_digest, x.approver_id, x.expires_at, x.nonce,
                    x.backup_digest, hmac.new(SECRET, _message(x), hashlib.sha256).hexdigest())


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, "approvals.sqlite")
        self.a = ApprovalStore(self.path)

    def tearDown(self):
        self.a.close()
        self.temp.cleanup()

    def test_quota_is_cumulative_and_persistent(self):
        self.assertTrue(self.a.reserve_daily_budget(4, now=100, daily_limit=10))
        self.assertTrue(self.a.reserve_daily_budget(6, now=100, daily_limit=10))
        self.assertFalse(self.a.reserve_daily_budget(1, now=100, daily_limit=10))
        self.a.close()
        self.a = ApprovalStore(self.path)
        self.assertFalse(self.a.reserve_daily_budget(1, now=101, daily_limit=10))
        self.assertTrue(self.a.reserve_daily_budget(1, now=86401, daily_limit=10))

    def test_invalid_quota_requests_rejected(self):
        self.assertFalse(self.a.reserve_daily_budget(11, now=100, daily_limit=10))
        self.assertFalse(self.a.reserve_daily_budget(True, now=100, daily_limit=10))

    def test_attempt_budget_covers_zero_match_scans_and_persists(self):
        self.assertTrue(self.a.reserve_attempt(now=100, hourly_limit=2, daily_limit=3))
        self.assertTrue(self.a.reserve_attempt(now=100, hourly_limit=2, daily_limit=3))
        self.assertFalse(self.a.reserve_attempt(now=100, hourly_limit=2, daily_limit=3))
        self.a.close()
        self.a = ApprovalStore(self.path)
        self.assertTrue(self.a.reserve_attempt(now=3700, hourly_limit=2, daily_limit=3))
        self.assertFalse(self.a.reserve_attempt(now=3700, hourly_limit=2, daily_limit=3))
        self.assertTrue(self.a.reserve_attempt(now=86401, hourly_limit=2, daily_limit=3))

    def test_once_only(self):
        self.a.register(signed("once"))
        self.assertTrue(self.a.consume("once", OP, SECRET, now=100))
        self.assertFalse(self.a.consume("once", OP, SECRET, now=100))

    def test_nonexistent_rejected(self):
        self.assertFalse(self.a.consume("unknown", OP, SECRET, now=100))

    def test_changed_operation_does_not_consume(self):
        self.a.register(signed("s"))
        self.assertFalse(self.a.consume("s", dict(OP, where={"status": "new"}), SECRET, now=100))
        self.assertTrue(self.a.consume("s", OP, SECRET, now=100))

    def test_expiration_rejected(self):
        self.a.register(signed("expired"))
        self.assertFalse(self.a.consume("expired", OP, SECRET, now=121))

    def test_persisted_replay_blocked(self):
        self.a.register(signed("durable"))
        self.assertTrue(self.a.consume("durable", OP, SECRET, now=100))
        self.a.close()
        self.a = ApprovalStore(self.path)
        self.assertFalse(self.a.consume("durable", OP, SECRET, now=100))


if __name__ == "__main__":
    unittest.main()
