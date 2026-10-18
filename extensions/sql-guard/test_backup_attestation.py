import gzip
import hashlib
import json
import os
import tempfile
import unittest

from backup_attestation import verify_backup


class BackupAttestationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = os.path.join(self.tmp.name, "trusted")
        os.mkdir(self.folder)
        os.chmod(self.folder, 0o700)
        self.archive = os.path.join(self.folder, "backup.sql.gz")
        with gzip.open(self.archive, "wb") as f:
            f.write(b"CREATE TABLE example (id INT);\n")
        with open(self.archive, "rb") as f:
            self.digest = hashlib.sha256(f.read()).hexdigest()
        self.manifest = os.path.join(self.folder, "manifest.json")
        self.data = {"archive": "backup.sql.gz", "sha256": self.digest,
                     "created_at": 100, "databases": ["sandbox"]}
        self.write_manifest()

    def write_manifest(self):
        with open(self.manifest, "w", encoding="utf-8") as f:
            json.dump(self.data, f)
        os.chmod(self.manifest, 0o600)

    def verify(self, **kwargs):
        return verify_backup({"database":"sandbox"}, self.digest,
            manifest_path=self.manifest, archive_dir=self.folder,
            owner_uid=os.getuid(), now=101, **kwargs)

    def tearDown(self):
        self.tmp.cleanup()

    def test_valid(self):
        self.assertTrue(self.verify())

    def test_digest_different(self):
        self.assertFalse(verify_backup({"database":"sandbox"}, "a"*64,
            manifest_path=self.manifest, archive_dir=self.folder,
            owner_uid=os.getuid(), now=101))

    def test_stale(self):
        self.data["created_at"] = 1
        self.write_manifest()
        self.assertFalse(self.verify(max_age=50))

    def test_other_database(self):
        self.data["databases"] = ["other"]
        self.write_manifest()
        self.assertFalse(self.verify())

    def test_untrusted_owner(self):
        self.assertFalse(verify_backup({"database":"sandbox"}, self.digest,
            manifest_path=self.manifest, archive_dir=self.folder,
            owner_uid=os.getuid() + 1, now=101))

    def test_corrupt_archive_matching_checksum(self):
        with open(self.archive, "wb") as f:
            f.write(b"invalid gzip")
        self.digest = hashlib.sha256(b"invalid gzip").hexdigest()
        self.data["sha256"] = self.digest
        self.write_manifest()
        self.assertFalse(self.verify())

    def test_symlink_archive(self):
        original = os.path.join(self.folder, "original")
        os.rename(self.archive, original)
        os.symlink(original, self.archive)
        self.assertFalse(self.verify())

    def test_group_writable_manifest_denied(self):
        os.chmod(self.manifest, 0o660)
        self.assertFalse(self.verify())


if __name__ == "__main__":
    unittest.main()
