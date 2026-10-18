import os
import unittest

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
