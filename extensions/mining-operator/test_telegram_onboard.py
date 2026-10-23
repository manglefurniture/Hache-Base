import importlib.util
import os
import subprocess
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location(
    "telegram_onboard", Path(__file__).with_name("telegram_onboard.py"))
import sys
sys.path.insert(0, str(Path(__file__).parent))
onboard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(onboard)


class FakeAPI:
    def __init__(self, updates):
        self.updates = updates
        self.called = []

    def call(self, method, data):
        self.called.append((method, data))
        return self.updates


def start(chat=222, user=222, text="/start", kind="private", update_id=4):
    return {"update_id": update_id, "message": {
        "chat": {"id": chat, "type": kind},
        "from": {"id": user, "is_bot": False}, "text": text}}


class OnboardTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.base = Path(self.folder.name) / "secure"
        self.base.mkdir(mode=0o700)
        self.own_uid = os.getuid()

    def tearDown(self):
        self.folder.cleanup()

    def test_unique_private_start(self):
        api = FakeAPI([start(), start(update_id=5), start(kind="group", update_id=6)])
        self.assertEqual(onboard.discover_private_start(api), (222, 222))
        self.assertEqual(api.called[0][0], "getUpdates")
        self.assertEqual(api.called[0][1]["allowed_updates"], ["message"])

    def test_group_or_non_start_ignored(self):
        api = FakeAPI([start(kind="supergroup"), start(text="hello")])
        with self.assertRaisesRegex(onboard.ProposalError, "no_private_start"):
            onboard.discover_private_start(api)

    def test_multiple_private_owners_rejected(self):
        api = FakeAPI([start(), start(chat=333, user=333)])
        with self.assertRaisesRegex(onboard.ProposalError, "ambiguous_private_starts"):
            onboard.discover_private_start(api)

    def test_sender_and_chat_not_assumed_same_identity(self):
        api = FakeAPI([start(chat=123, user=456)])
        self.assertEqual(onboard.discover_private_start(api), (123, 456))

    def test_write_recipient_is_private_and_no_overwrite(self):
        path = self.base / "telegram-recipient.env"
        onboard.write_recipient(123, 456, path=path, owner_uid=self.own_uid)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(path.read_text(),
                         "HACHE_TELEGRAM_CHAT_ID=123\nHACHE_TELEGRAM_USER_ID=456\n")
        with self.assertRaisesRegex(onboard.ProposalError, "recipient_already_configured"):
            onboard.write_recipient(999, 999, path=path, owner_uid=self.own_uid)
        self.assertNotIn("999", path.read_text())

    def test_reject_untrusted_directory(self):
        path = self.base / "telegram-recipient.env"
        self.base.chmod(0o755)
        with self.assertRaisesRegex(onboard.ProposalError, "untrusted_recipient_directory"):
            onboard.write_recipient(123, 456, path=path, owner_uid=self.own_uid)

    def test_token_private_permissions_and_no_symlink(self):
        token_file = self.base / "telegram_token"
        token = "1234567:" + "a"*35
        token_file.write_text(token)
        token_file.chmod(0o600)
        self.assertEqual(onboard.read_token(token_file, self.own_uid), token)
        token_file.chmod(0o644)
        with self.assertRaisesRegex(onboard.ProposalError, "untrusted_bot_token"):
            onboard.read_token(token_file, self.own_uid)
        token_file.chmod(0o600)
        link = self.base / "link_token"
        link.symlink_to(token_file)
        with self.assertRaises(OSError):
            onboard.read_token(link, self.own_uid)

    def test_invalid_token_rejected(self):
        token_file = self.base / "telegram_token"
        token_file.write_text("not a telegram token")
        token_file.chmod(0o600)
        with self.assertRaisesRegex(onboard.ProposalError, "invalid_bot_token"):
            onboard.read_token(token_file, self.own_uid)

    def test_install_script_syntax_and_scope(self):
        installer = Path(__file__).parent / "deploy" / "install-telegram-proposals.sh"
        result = subprocess.run(["bash", "-n", str(installer)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        contents = installer.read_text()
        self.assertIn("TELEGRAM_TEST_MESSAGE_SENT", contents)
        self.assertIn("systemctl enable --now hache-mining-agent-telegram.service", contents)
        self.assertNotIn("systemctl restart hache-mining-operator", contents)
        self.assertNotIn("sudoers", contents)

    def test_service_template_separates_credential_and_state(self):
        unit = (Path(__file__).parent / "deploy" /
                "hache-mining-agent-telegram.service.example").read_text()
        self.assertIn("LoadCredential=telegram_token:", unit)
        self.assertIn("EnvironmentFile=/etc/hache-mining-agent/telegram-recipient.env", unit)
        self.assertIn("StateDirectory=hache-mining-telegram", unit)
        self.assertIn("NoNewPrivileges=yes", unit)
        self.assertNotIn("REPLACE_PRIVATE_CHAT_ID", unit)
        self.assertNotIn("ExecStart=/bin/sh", unit)


if __name__ == "__main__":
    unittest.main()
