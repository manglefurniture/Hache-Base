import hashlib
import hmac
import os
import tempfile
import unittest

from approval import Approval, _message, canonical_operation
from approval_store import ApprovalStore
from authorized_runner import ApprovalRequired, RunnerConfig, execute_guarded
from mariadb_executor import UnsafeMutation

SECRET = b"runner-independent-test-secret-at-least-32-bytes"
SCHEMA = {"sandbox": {"items": {"id", "status"}}}
PKS = {"sandbox": {"items": "id"}}
CONFIG = RunnerConfig(SCHEMA, PKS)
BASE = {"database": "sandbox", "table": "items", "operation": "delete",
        "where": {"status": "old"}, "values": {}}


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection
        self.rowcount = 0
    def execute(self, sql, args=None):
        self.connection.commands.append((sql, args))
        if sql.startswith("DELETE"):
            self.rowcount = self.connection.count
        elif sql.startswith("UPDATE"):
            self.rowcount = self.connection.count
    def fetchall(self):
        return [(i,) for i in range(self.connection.count)]
    def close(self):
        pass


class FakeConnection:
    def __init__(self, count=1):
        self.count = count
        self.commands = []
        self.committed = False
        self.rolled_back = False
    def cursor(self):
        return FakeCursor(self)
    def commit(self):
        self.committed = True
    def rollback(self):
        self.rolled_back = True


class GuardedRunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = ApprovalStore(os.path.join(self.tmp.name, "approvals.db"))
    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()
    def approval(self, operation, nonce="only-one"):
        unsigned = Approval(canonical_operation(operation), "owner-123",
                            200, nonce, "a"*64, "")
        signature = hmac.new(SECRET, _message(unsigned), hashlib.sha256).hexdigest()
        a = Approval(unsigned.operation_digest, unsigned.approver_id,
                     unsigned.expires_at, unsigned.nonce,
                     unsigned.backup_digest, signature)
        self.store.register(a)
        return a
    def execute_change(self, conn, operation, *, nonce=None, backup_checker=None):
        return execute_guarded(conn, self.store, operation, config=CONFIG,
                               nonce=nonce, verifier_key=SECRET,
                               backup_checker=backup_checker, now=100)

    def test_small_change_needs_no_approval(self):
        c = FakeConnection(count=2)
        self.assertEqual(self.execute_change(c, BASE), 2)
        self.assertTrue(c.committed)

    def test_mass_write_without_approval_does_not_touch_db(self):
        c = FakeConnection(count=11)
        op = dict(BASE, expected_rows=11)
        with self.assertRaises(ApprovalRequired):
            self.execute_change(c, op)
        self.assertFalse(c.commands)

    def test_approved_mass_delete(self):
        c = FakeConnection(count=11)
        op = dict(BASE, expected_rows=11)
        self.approval(op)
        checked = []
        def verify(operation, checksum):
            checked.append((operation, checksum))
            return True
        self.assertEqual(self.execute_change(c, op, nonce="only-one", backup_checker=verify), 11)
        self.assertTrue(c.committed)
        self.assertEqual(checked[0], (op, "a"*64))
        self.assertEqual(self.store.db.execute(
            "SELECT phase FROM execution_events WHERE nonce='only-one' ORDER BY id DESC"
        ).fetchone()[0], "committed")

    def test_replay_is_rejected_without_new_write(self):
        op = dict(BASE, expected_rows=11)
        self.approval(op)
        self.execute_change(FakeConnection(count=11), op, nonce="only-one", backup_checker=lambda *_: True)
        c = FakeConnection(count=11)
        with self.assertRaises(ApprovalRequired):
            self.execute_change(c, op, nonce="only-one", backup_checker=lambda *_: True)
        self.assertFalse(c.commands)

    def test_changed_operation_rejected_and_nonce_retained(self):
        op = dict(BASE, expected_rows=11)
        self.approval(op)
        mutated = dict(op, where={"status": "active"})
        c = FakeConnection(count=11)
        with self.assertRaises(ApprovalRequired):
            self.execute_change(c, mutated, nonce="only-one", backup_checker=lambda *_: True)
        self.assertFalse(c.commands)
        self.assertEqual(self.store.db.execute("SELECT used FROM approvals").fetchone()[0], 0)

    def test_unverified_backup_blocks(self):
        op = dict(BASE, expected_rows=11)
        self.approval(op)
        with self.assertRaises(ApprovalRequired):
            self.execute_change(FakeConnection(11), op, nonce="only-one", backup_checker=lambda *_: False)
        self.assertEqual(self.store.db.execute("SELECT used FROM approvals").fetchone()[0], 0)

    def test_locked_row_count_change_burns_approval(self):
        op = dict(BASE, expected_rows=11)
        self.approval(op)
        c = FakeConnection(count=12)
        with self.assertRaises(UnsafeMutation):
            self.execute_change(c, op, nonce="only-one", backup_checker=lambda *_: True)
        self.assertTrue(c.rolled_back)
        self.assertEqual(self.store.db.execute("SELECT used FROM approvals").fetchone()[0], 1)
        self.assertEqual(self.store.db.execute(
            "SELECT phase FROM execution_events ORDER BY id DESC"
        ).fetchone()[0], "failed_or_unknown")

    def test_cap_is_hard(self):
        op = dict(BASE, expected_rows=1001)
        with self.assertRaises(ValueError):
            self.execute_change(FakeConnection(), op)

    def test_unscoped_rejected(self):
        op = dict(BASE, where={})
        with self.assertRaises(UnsafeMutation):
            self.execute_change(FakeConnection(), op)


if __name__ == "__main__":
    unittest.main()
