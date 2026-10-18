import unittest
from mariadb_executor import Change, UnsafeMutation, apply

SCHEMA = {"sandbox": {"items": {"id", "status"}}}
PKS = {"sandbox": {"items": "id"}}

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
        n = apply(db, Change("sandbox", "items", "update", {"id": 1}, {"status": "ok"}), SCHEMA, primary_keys=PKS)
        self.assertEqual(n, 1)
        self.assertTrue(db.committed)
        self.assertIn("FOR UPDATE", db.cur.commands[1][0])
        self.assertEqual(db.cur.commands[2][1], ["ok", 1])
        self.assertIn("WHERE `id` IN", db.cur.commands[2][0])
    def test_primary_key_required(self):
        with self.assertRaises(UnsafeMutation):
            apply(Connection(), Change("sandbox", "items", "update", {"id": 1}, {"status": "x"}), SCHEMA, primary_keys={})
    def test_primary_key_cannot_be_changed(self):
        with self.assertRaises(UnsafeMutation):
            apply(Connection(), Change("sandbox", "items", "update", {"id": 1}, {"id": 2}), SCHEMA, primary_keys=PKS)
    def test_mass_delete_rollback(self):
        db = Connection(count=11)
        with self.assertRaises(UnsafeMutation):
            apply(db, Change("sandbox", "items", "delete", {"status": "x"}, {}), SCHEMA, primary_keys=PKS)
        self.assertTrue(db.rolled_back)
        self.assertEqual(len(db.cur.commands), 2)
    def test_delete_count_mismatch_rollback(self):
        db = Connection(count=2, rowcount=1)
        with self.assertRaises(UnsafeMutation):
            apply(db, Change("sandbox", "items", "delete", {"status": "x"}, {}), SCHEMA, primary_keys=PKS)
        self.assertTrue(db.rolled_back)
    def test_unscoped_refused(self):
        with self.assertRaises(UnsafeMutation):
            apply(Connection(), Change("sandbox", "items", "delete", {}, {}), SCHEMA, primary_keys=PKS)
    def test_identifier_injection_refused(self):
        with self.assertRaises(UnsafeMutation):
            apply(Connection(), Change("sandbox", "items; DROP TABLE items", "update", {"id": 1}, {"status": "x"}), SCHEMA, primary_keys=PKS)
    def test_value_bound(self):
        db = Connection()
        payload = "x'; DROP TABLE items;--"
        apply(db, Change("sandbox", "items", "update", {"id": 1}, {"status": payload}), SCHEMA, primary_keys=PKS)
        self.assertEqual(db.cur.commands[2][1][0], payload)

if __name__ == "__main__":
    unittest.main()
