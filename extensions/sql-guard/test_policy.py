import unittest
from policy import Request, Decision, decide

DATABASES = {"hache_natacion", "hache_miner"}

class PolicyTests(unittest.TestCase):
    def test_read_allowed(self):
        self.assertEqual(decide(Request("select", "hache_natacion"), DATABASES), Decision.ALLOW)
    def test_unknown_database_denied(self):
        self.assertEqual(decide(Request("select", "mysql"), DATABASES), Decision.DENY)
    def test_unknown_operation_denied(self):
        self.assertEqual(decide(Request("grant", "hache_natacion"), DATABASES), Decision.DENY)
    def test_missing_count_denied(self):
        self.assertEqual(decide(Request("delete", "hache_natacion", has_where=True), DATABASES), Decision.DENY)
    def test_mass_update_requires_approval(self):
        self.assertEqual(decide(Request("update", "hache_miner", 100, True), DATABASES), Decision.APPROVAL_REQUIRED)
    def test_approval_alone_insufficient(self):
        self.assertEqual(decide(Request("delete", "hache_natacion", 100, True, False, True), DATABASES), Decision.APPROVAL_REQUIRED)
    def test_backup_and_approval(self):
        self.assertEqual(decide(Request("delete", "hache_natacion", 100, True, True, True), DATABASES), Decision.ALLOW)
    def test_destructive_requires_both(self):
        self.assertEqual(decide(Request("drop", "hache_natacion", backed_up=True), DATABASES), Decision.APPROVAL_REQUIRED)
    def test_small_scoped_write(self):
        self.assertEqual(decide(Request("update", "hache_natacion", 2, True), DATABASES), Decision.ALLOW)
    def test_unscoped_delete(self):
        self.assertEqual(decide(Request("delete", "hache_natacion", 1, False), DATABASES), Decision.APPROVAL_REQUIRED)

if __name__ == "__main__":
    unittest.main()
