"""Safe first-run trusted-backup template contract tests (no production dumps)."""
import pathlib
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parent
SCRIPT = ROOT / "deploy" / "create-trusted-backup.sh.example"


class TrustedBackupTemplateTests(unittest.TestCase):
    def test_shell_syntax(self):
        subprocess.run(["bash", "-n", str(SCRIPT)], check=True)

    def test_requires_real_root_and_private_directory(self):
        src = SCRIPT.read_text()
        self.assertIn('EUID', src)
        self.assertIn('EXPECTED_GROUP="sqlguard-store"', src)
        self.assertIn('flock -n 9', src)

    def test_reserve_disk_and_avoid_auto_deletion(self):
        src = SCRIPT.read_text()
        self.assertIn("free_bytes", src)
        self.assertIn("4294967296", src)
        self.assertNotIn(" -delete", src)

    def test_verified_backup_before_atomic_manifest(self):
        src = SCRIPT.read_text()
        self.assertIn('set -euo pipefail', src)
        self.assertIn('mariadb-dump --no-defaults --user=root --socket=/run/mysqld/mysqld.sock', src)
        self.assertIn('--single-transaction --quick --routines --events --triggers', src)
        self.assertIn('--databases "${DATABASES[@]}"', src)
        self.assertIn('gzip -t "$tmp/$archive"', src)
        self.assertIn('sha256sum "$tmp/$archive"', src)
        self.assertIn('chown root:"$EXPECTED_GROUP"', src)
        self.assertLess(src.index('mv -- "$tmp/$archive" "$OUT/$archive"'),
                        src.index('mv -- "$tmp/manifest.json" "$OUT/manifest.json"'))

    def test_no_prod_writes_or_sql_privilege_changes(self):
        src = SCRIPT.read_text()
        for forbidden in ("CREATE USER ", "GRANT ", "REVOKE ", "DROP DATABASE ",
                          "mariadb -e ", "systemctl start ", "systemctl enable ",
                          "usermod ", "rm -rf /var/lib/mysql"):
            self.assertNotIn(forbidden, src)


if __name__ == "__main__":
    unittest.main()
