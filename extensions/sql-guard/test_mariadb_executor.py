import unittest
from mariadb_executor import Change, UnsafeMutation, apply

SCHEMA = {"sandbox": {"items": {"id", "status"}}}

class Cursor:
    def __init__(self, count=1, rowcount=1):
        self.count = count
        self.rowcount = rowcount
        self.commands = []
    def execute(self, sql, args=None):
        self.commands.append((sql, args))
    def fetchall(self):
        return [(1,)] * self.count
    def close(self):
        pass

class Connection:
    def __init__(self, count=1, rowcount=1):
        self.cur = Cursor(count, rowcount)
        self.committed = self.rolled_back = False
    def cursor(self):
        return self.cur
    def commit(self):
        self.committed = True
    def rollback(self):
        self.rolled_back = True

class MariaDBExecutorTests(unittest.TestCase):
    def test_small_update(self):
        db = Connection()
        n = apply(db, Change("sandbox", "items", "update", {"id": 1}, {"status": "ok"}), SCHEMA)
        self.assertEqual(n, 1)
        self.assertTrue(db.committed)
        self.assertIn("FOR UPDATE", db.cur.commands[1][0])
        self.assertEqual(db.cur.commands[2][1], ["ok", 1])
    def test_mass_delete_rollback(self):
        db = Connection(count=11)
        with self.assertRaises(UnsafeMutation):
            apply(db, Change("sandbox", "items", "delete", {"status": "x"}, {}), SCHEMA)
        self.assertTrue(db.rolled_back)
        self.assertEqual(len(db.cur.commands), 2)
    def test_delete_count_mismatch_rollback(self):
        db = Connection(count=2, rowcount=1)
        with self.assertRaises(UnsafeMutation):
            apply(db, Change("sandbox", "items", "delete", {"status": "x"}, {}), SCHEMA)
        self.assertTrue(db.rolled_back)
    def test_unscoped_refused(self):
        with self.assertRaises(UnsafeMutation):
            apply(Connection(), Change("sandbox", "items", "delete", {}, {}), SCHEMA)
    def test_identifier_injection_refused(self):
        with self.assertRaises(UnsafeMutation):
            apply(Connection(), Change("sandbox", "items; DROP TABLE items", "update", {"id": 1}, {"status": "x"}), SCHEMA)
    def test_value_bound(self):
        db = Connection()
        payload = "x'; DROP TABLE items;--"
        apply(db, Change("sandbox", "items", "update", {"id": 1}, {"status": payload}), SCHEMA)
        self.assertEqual(db.cur.commands[2][1][0], payload)

if __name__ == "__main__":
    unittest.main()
