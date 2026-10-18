import sqlite3
import unittest

from executor import GuardRejected, Mutation, execute_mutation

SCHEMA = {"sandbox": {"items": {"id", "group_id", "note"}}}


class ExecutorTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, group_id INTEGER, note TEXT)")
        self.conn.executemany(
            "INSERT INTO items(id, group_id, note) VALUES (?, ?, ?)",
            [(i, 1 if i <= 11 else 2, "original") for i in range(1, 14)],
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_small_update(self):
        count = execute_mutation(self.conn, Mutation("sandbox", "items", "update", {"id": 1}, {"note": "updated"}), tables=SCHEMA)
        self.assertEqual(count, 1)
        self.assertEqual(self.conn.execute("SELECT note FROM items WHERE id=1").fetchone()[0], "updated")

    def test_small_delete(self):
        count = execute_mutation(self.conn, Mutation("sandbox", "items", "delete", {"id": 13}, {}), tables=SCHEMA)
        self.assertEqual(count, 1)

    def test_large_update_rolls_back(self):
        with self.assertRaises(GuardRejected):
            execute_mutation(self.conn, Mutation("sandbox", "items", "update", {"group_id": 1}, {"note": "changed"}), tables=SCHEMA)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM items WHERE note='changed'").fetchone()[0], 0)

    def test_mass_delete_rolls_back(self):
        with self.assertRaises(GuardRejected):
            execute_mutation(self.conn, Mutation("sandbox", "items", "delete", {"group_id": 1}, {}), tables=SCHEMA)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM items").fetchone()[0], 13)

    def test_injection_identifier_blocked(self):
        with self.assertRaises(GuardRejected):
            execute_mutation(self.conn, Mutation("sandbox", "items; DROP TABLE items", "delete", {"id": 1}, {}), tables=SCHEMA)

    def test_no_predicate(self):
        with self.assertRaises(GuardRejected):
            execute_mutation(self.conn, Mutation("sandbox", "items", "delete", {}, {}), tables=SCHEMA)

    def test_unlisted_column(self):
        with self.assertRaises(GuardRejected):
            execute_mutation(self.conn, Mutation("sandbox", "items", "update", {"id": 1}, {"password": "foo"}), tables=SCHEMA)

    def test_sql_injection_value_is_bound(self):
        value = "'); DROP TABLE items; --"
        execute_mutation(self.conn, Mutation("sandbox", "items", "update", {"id": 1}, {"note": value}), tables=SCHEMA)
        self.assertEqual(self.conn.execute("SELECT note FROM items WHERE id=1").fetchone()[0], value)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM items").fetchone()[0], 13)


if __name__ == "__main__":
    unittest.main()
