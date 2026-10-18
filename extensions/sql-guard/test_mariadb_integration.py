import os
import unittest
import hashlib
import hmac
import tempfile

from approval import Approval, _message, canonical_operation
from approval_store import ApprovalStore
from authorized_runner import ApprovalRequired, RunnerConfig, execute_guarded

from mariadb_executor import Change, UnsafeMutation, apply

try:
    import pymysql
except ImportError:
    pymysql = None

SCHEMA = {"sandbox": {"items": {"id", "status"}}}
PKS = {"sandbox": {"items": "id"}}


@unittest.skipUnless(os.getenv("SQLGUARD_MARIADB_TEST") == "1" and pymysql, "MariaDB integration environment required")
class MariaDBIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = pymysql.connect(host="127.0.0.1", user="guardtest",
            password="local-test-password", database="sandbox", autocommit=True)
        with cls.db.cursor() as c:
            c.execute("CREATE TABLE IF NOT EXISTS items (id INT PRIMARY KEY, status VARCHAR(50)) ENGINE=InnoDB")

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def setUp(self):
        with self.db.cursor() as c:
            c.execute("DELETE FROM items")
            c.executemany("INSERT INTO items VALUES (%s,%s)", [(i, "old") for i in range(1, 14)])

    def test_signed_mass_delete_one_time(self):
        # Isolated MariaDB test: the approval and trusted backup are fixtures,
        # NOT a test of production credentials or human WebAuthn.
        with self.db.cursor() as cur:
            cur.execute("UPDATE items SET status='keep' WHERE id>=12")
        operation = {"database": "sandbox", "table": "items", "operation": "delete",
                     "where": {"status": "old"}, "values": {}, "expected_rows": 11}
        secret = b"a-trusted-local-test-signing-key-32bytes"
        a = Approval(canonical_operation(operation), "test-owner", 200,
                     "one-use-only", "a"*64, "")
        signature = hmac.new(secret, _message(a), hashlib.sha256).hexdigest()
        signed = Approval(a.operation_digest, a.approver_id, a.expires_at,
                          a.nonce, a.backup_digest, signature)
        with tempfile.TemporaryDirectory() as tmp:
            store = ApprovalStore(os.path.join(tmp, "signed.db"))
            try:
                store.register(signed)
                config = RunnerConfig(SCHEMA, PKS)
                self.assertEqual(execute_guarded(
                    self.db, store, operation, config=config, nonce=a.nonce,
                    verifier_key=secret, backup_checker=lambda *_: True,
                    now=100), 11)
                with self.db.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM items")
                    self.assertEqual(cur.fetchone()[0], 2)
                    cur.execute("SELECT COUNT(*) FROM items WHERE status='keep'")
                    self.assertEqual(cur.fetchone()[0], 2)
                with self.assertRaises(ApprovalRequired):
                    execute_guarded(
                        self.db, store, operation, config=config, nonce=a.nonce,
                        verifier_key=secret, backup_checker=lambda *_: True,
                        now=100)
            finally:
                store.close()

    def test_approved_mass_count_mismatch_rolls_back(self):
        operation = {"database": "sandbox", "table": "items", "operation": "delete",
                     "where": {"status": "old"}, "values": {}, "expected_rows": 11}
        secret = b"a-trusted-local-test-signing-key-32bytes"
        a = Approval(canonical_operation(operation), "test-owner", 200,
                     "mismatch-only", "a"*64, "")
        signed = Approval(a.operation_digest, a.approver_id, a.expires_at,
                          a.nonce, a.backup_digest,
                          hmac.new(secret, _message(a), hashlib.sha256).hexdigest())
        with tempfile.TemporaryDirectory() as tmp:
            store = ApprovalStore(os.path.join(tmp, "signed.db"))
            try:
                store.register(signed)
                with self.assertRaises(UnsafeMutation):
                    execute_guarded(
                        self.db, store, operation,
                        config=RunnerConfig(SCHEMA, PKS), nonce=a.nonce,
                        verifier_key=secret, backup_checker=lambda *_: True, now=100)
                with self.db.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM items")
                    self.assertEqual(cur.fetchone()[0], 13)
            finally:
                store.close()

    def test_small_update_and_rollback(self):
        self.assertEqual(apply(self.db, Change("sandbox", "items", "update",
            {"id": 1}, {"status": "new"}), SCHEMA, primary_keys=PKS), 1)
        with self.db.cursor() as c:
            c.execute("SELECT status FROM items WHERE id=1")
            self.assertEqual(c.fetchone()[0], "new")

    def test_mass_update_refused(self):
        with self.assertRaises(UnsafeMutation):
            apply(self.db, Change("sandbox", "items", "update",
                {"status": "old"}, {"status": "new"}), SCHEMA, primary_keys=PKS)
        with self.db.cursor() as c:
            c.execute("SELECT COUNT(*) FROM items WHERE status='new'")
            self.assertEqual(c.fetchone()[0], 0)

    def test_unscoped_delete_refused(self):
        with self.assertRaises(UnsafeMutation):
            apply(self.db, Change("sandbox", "items", "delete", {}, {}), SCHEMA, primary_keys=PKS)
        with self.db.cursor() as c:
            c.execute("SELECT COUNT(*) FROM items")
            self.assertEqual(c.fetchone()[0], 13)

    def test_single_delete(self):
        self.assertEqual(apply(self.db, Change("sandbox", "items", "delete",
            {"id": 1}, {}), SCHEMA, primary_keys=PKS), 1)
