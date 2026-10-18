"""Offline tests for the root-operated SQL Guard approval credential helper."""
import hashlib
import importlib.util
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
MODULE = ROOT / "deploy" / "prepare-approval-credentials.py"

spec = importlib.util.spec_from_file_location("sqlguard_prepare_approval_credentials", MODULE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class ApprovalCredentialPreparationTests(unittest.TestCase):
    def test_material_is_random_and_linked_to_hash(self):
        first, token1 = mod.create_material()
        second, token2 = mod.create_material()
        self.assertNotEqual(first, second)
        self.assertNotEqual(token1, token2)
        values = dict(line.split("=", 1) for line in first.splitlines())
        self.assertEqual(values["SQLGUARD_ORIGIN"],
                         "https://aprobaciones.hacheinteractive.com")
        self.assertEqual(values["SQLGUARD_BOOTSTRAP_HASH"],
                         hashlib.sha256(token1.strip().encode()).hexdigest())
        self.assertEqual(len(bytes.fromhex(values["SQLGUARD_SIGN_KEY_HEX"])), 32)
        self.assertGreaterEqual(len(values["SQLGUARD_AGENT_TOKEN"]), 32)
        self.assertNotIn(token1.strip(), first)
        self.assertIn("SQLGUARD_BACKUP_MANIFEST", values)

    def test_exclusive_creation_private_modes_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            e = root / "approval.env"
            t = root / "enrollment-token"
            env, token = mod.create_material()
            mod.create_pair(e, t, env, token, owner_uid=os.geteuid())
            self.assertEqual(stat.S_IMODE(e.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(t.stat().st_mode), 0o600)
            self.assertEqual(e.read_text(), env)
            self.assertEqual(t.read_text(), token)
            with self.assertRaises(FileExistsError):
                mod.create_pair(e, t, "OVERWRITE", "OVERWRITE", owner_uid=os.geteuid())
            self.assertEqual(e.read_text(), env)

    def test_token_write_failure_removes_partial_file(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            env, token = mod.create_material()
            with patch.object(mod.os, "fsync", side_effect=OSError("simulated disk failure")):
                with self.assertRaises(OSError):
                    mod.create_pair(root / "approval.env", root / "enrollment-token",
                                    env, token, owner_uid=os.geteuid())
            self.assertFalse((root / "enrollment-token").exists())
            self.assertFalse((root / "approval.env").exists())

    def test_env_write_failure_removes_both_partial_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            env, token = mod.create_material()
            with patch.object(mod.os, "fsync", side_effect=[None, OSError("simulated disk failure")]):
                with self.assertRaises(OSError):
                    mod.create_pair(root / "approval.env", root / "enrollment-token",
                                    env, token, owner_uid=os.geteuid())
            self.assertFalse((root / "enrollment-token").exists())
            self.assertFalse((root / "approval.env").exists())

    def test_symlink_destination_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root / "target"
            target.write_text("must survive")
            (root / "enrollment-token").symlink_to(target)
            with self.assertRaises(FileExistsError):
                mod.create_pair(root / "approval.env", root / "enrollment-token",
                                "dummy", "dummy", owner_uid=os.geteuid())
            self.assertEqual(target.read_text(), "must survive")
            self.assertFalse((root / "approval.env").exists())

    def test_check_mode_is_read_only(self):
        result = subprocess.run(
            [sys.executable, str(MODULE), "--check"],
            capture_output=True, text=True, timeout=10, check=True)
        self.assertIn("CHECK_ONLY: no changes", result.stdout)
        self.assertNotIn("SQLGUARD_SIGN_KEY_HEX", result.stdout)

    def test_non_root_rejected_for_apply(self):
        if os.geteuid() == 0:
            self.skipTest("CI is normally unprivileged")
        result = subprocess.run([sys.executable, str(MODULE), "--apply"],
                                capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("root is required", result.stderr)


if __name__ == "__main__":
    unittest.main()
