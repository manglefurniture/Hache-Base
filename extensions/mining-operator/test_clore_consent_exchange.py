"""No-spend isolated Telegram-to-finance signed-consent exchange regression."""
from datetime import datetime, timezone
import copy
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding, NoEncryption, PrivateFormat, PublicFormat
)

from clore_cancel_guard import db_open
from clore_consent_attestation import init_ledger_schema
from clore_consent_exchange import (
    ExchangeError, _checked_regular, _read_key, export_json, import_json, migrate_ledger
)
from clore_preorder import reserve
from telegram_proposals import ProposalStore

NOW = 1800000000
IMAGE = "ghcr.io/manglefurniture/prl-miner@sha256:" + "a" * 64


class Inventory:
    def inventory(self):
        return {"limit": 10, "orders": []}


class ExchangeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.tg = ProposalStore(str(self.root / "tg.sqlite"))
        self.addCleanup(self.tg.close)
        self.finance = db_open(self.root / "finance.sqlite")
        self.addCleanup(self.finance.close)
        init_ledger_schema(self.finance)
        self.finance.execute("INSERT INTO clore_cancel_heartbeat VALUES(1,?)", (NOW,))
        private = Ed25519PrivateKey.generate()
        self.private = private.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
        self.public = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        self.terms = {
            "server_id": 456, "currency": "USD-Blockchain",
            "gpu_descriptor": "1x NVIDIA GeForce RTX 5090",
            "gpu_variant": "desktop", "gpu_variant_verified": True,
            "image": IMAGE, "daily_bid_usd": "12", "max_total_usd": "1",
            "creation_fee_usd": "0.10", "max_minutes": 60,
            "quote_observed_at": datetime.fromtimestamp(NOW - 10, timezone.utc).isoformat()
        }
        prepared = self.tg.prepare_clore(self.terms, now=datetime.fromtimestamp(NOW, timezone.utc))
        self.nonce = prepared["proposal_id"]
        self.tg.mark_clore_notified(self.nonce, 77, NOW)
        self.reservation_id = reserve(
            self.finance, terms=self.terms, api=Inventory(), now=NOW,
            timer_check=True)["reservation_id"]

    def accept(self):
        reply = self.tg.process_update({
            "update_id": 10,
            "callback_query": {
                "id": "callback", "data": "clore-accept:" + self.nonce,
                "from": {"id": 11},
                "message": {"message_id": 77, "chat": {"id": 11, "type": "private"}}
            }}, 11, 11, NOW)
        self.assertEqual(reply["state"], "clore_acknowledged")

    def export(self):
        return export_json(self.tg.db, nonce=self.nonce,
                           private_key_raw=self.private, now=NOW).encode("utf-8")

    def imported(self, wire):
        return import_json(self.finance, wire=wire,
                           trusted_public_key_raw=self.public,
                           reservation_id=self.reservation_id,
                           now=NOW, timer_check=True)

    def test_full_consent_exchange_is_not_a_spend_grant(self):
        self.accept()
        wire = self.export()
        self.assertNotIn(self.private.hex().encode(), wire)
        result = self.imported(wire)
        self.assertEqual(result, {"consent_recorded": True,
                                  "rental_permitted": False,
                                  "provider_mutation": False})
        self.assertEqual(self.finance.execute(
            "SELECT state FROM clore_consent_receipts").fetchone()[0], "verified_only")
        self.assertEqual(self.finance.execute(
            "SELECT COUNT(*) FROM clore_cancel_leases").fetchone()[0], 0)
        self.assertEqual(self.finance.execute(
            "SELECT phase FROM clore_preorders").fetchone()[0], "reserved")

    def test_explicit_finance_migration_is_required_and_idempotent(self):
        self.accept()
        wire = self.export()
        self.finance.execute("DROP TABLE clore_consent_receipts")
        with self.assertRaisesRegex(Exception, "consent_ledger_schema_missing"):
            self.imported(wire)
        self.assertEqual(migrate_ledger(self.finance),
                         {"schema_ready": True, "rental_permitted": False})
        self.assertEqual(migrate_ledger(self.finance),
                         {"schema_ready": True, "rental_permitted": False})
        self.assertTrue(self.imported(wire)["consent_recorded"])

    def test_unapproved_proposal_cannot_be_exported(self):
        with self.assertRaises(Exception):
            self.export()

    def test_replay_is_denied_after_commit(self):
        self.accept()
        wire = self.export()
        self.imported(wire)
        with self.assertRaisesRegex(Exception, "already_used"):
            self.imported(wire)

    def test_invalid_or_oversize_transport_denied(self):
        for wire in (b"", b"{", b"[]", b"0", b" " * 4097):
            with self.subTest(wire=wire[:10]), self.assertRaises(ExchangeError):
                self.imported(wire)
        self.assertEqual(self.finance.execute(
            "SELECT COUNT(*) FROM clore_consent_receipts").fetchone()[0], 0)

    def test_modified_contract_signature_or_wrong_key_denied(self):
        self.accept()
        receipt = json.loads(self.export())
        receipt["statement"]["terms_sha256"] = "f" * 64
        with self.assertRaises(Exception):
            self.imported(json.dumps(receipt).encode())
        self.public = Ed25519PrivateKey.generate().public_key().public_bytes(
            Encoding.Raw, PublicFormat.Raw)
        with self.assertRaises(Exception):
            self.imported(self.export())

    def test_unhealthy_timer_blocks_finance_import(self):
        self.accept()
        with self.assertRaises(Exception):
            import_json(self.finance, wire=self.export(),
                        trusted_public_key_raw=self.public,
                        reservation_id=self.reservation_id, now=NOW,
                        timer_check=False)

    def test_key_file_rejects_symlinks_hardlinks_and_permissive_mode(self):
        key = self.root / "key"
        key.write_bytes(self.private)
        os.chmod(key, 0o600)
        self.assertEqual(_read_key(key, owner_uid=os.geteuid(), private=True), self.private)
        os.chmod(key, 0o644)
        with self.assertRaises(ExchangeError):
            _read_key(key, owner_uid=os.geteuid(), private=True)
        os.chmod(key, 0o600)
        link = self.root / "link"
        link.symlink_to(key)
        with self.assertRaises(OSError):
            _read_key(link, owner_uid=os.geteuid(), private=True)
        link.unlink()
        os.link(key, link)
        with self.assertRaises(ExchangeError):
            _checked_regular(key, owner_uid=os.geteuid(), private=True)


if __name__ == "__main__":
    unittest.main()
