"""Signed Clore Telegram receipt, no real orders, no shared DB or private key."""
from datetime import datetime, timezone
import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding, PrivateFormat, PublicFormat, NoEncryption
)

from clore_cancel_guard import db_open
from clore_preorder import reserve
from clore_consent_attestation import (
    ConsentError, issue_receipt, verify_receipt, init_ledger_schema,
    record_verified_consent
)
from telegram_proposals import ProposalStore

NOW = 1800000000
IMAGE = "ghcr.io/manglefurniture/prl-miner@sha256:" + "a" * 64


def terms(**changes):
    t = {
        "server_id": 456, "currency": "USD-Blockchain",
        "gpu_descriptor": "1x NVIDIA GeForce RTX 5090",
        "gpu_variant": "desktop", "gpu_variant_verified": True,
        "image": IMAGE, "daily_bid_usd": "12", "max_total_usd": "1",
        "creation_fee_usd": "0.10", "max_minutes": 60,
        "quote_observed_at": datetime.fromtimestamp(NOW-10, timezone.utc).isoformat()
    }
    t.update(changes)
    return t


class Inventory:
    def inventory(self):
        return {"limit": 10, "orders": []}


class AttestationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)
        self.telegram = ProposalStore(str(self.path/"telegram.sqlite3"))
        self.guard = db_open(self.path/"finance.sqlite3")
        init_ledger_schema(self.guard)
        self.guard.execute("INSERT INTO clore_cancel_heartbeat VALUES(1,?)", (NOW,))
        private = Ed25519PrivateKey.generate()
        self.private = private.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
        self.public = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        self.proposal = self.telegram.prepare_clore(
            terms(), now=datetime.fromtimestamp(NOW, timezone.utc))
        self.nonce = self.proposal["proposal_id"]
        self.telegram.mark_clore_notified(self.nonce, 77, NOW)
        self.reservation = reserve(
            self.guard, terms=terms(), api=Inventory(), now=NOW, timer_check=True
        )["reservation_id"]

    def tearDown(self):
        self.telegram.close()
        self.guard.close()
        self.temp.cleanup()

    def decide(self, decision="accept", tick=NOW, update_id=1):
        return self.telegram.process_update({
            "update_id": update_id,
            "callback_query": {
                "id": "telegram-callback", "data": f"clore-{decision}:{self.nonce}",
                "from": {"id": 11},
                "message": {"message_id": 77, "chat": {"id": 11, "type": "private"}}
            }
        }, 11, 11, tick)

    def signed(self):
        self.assertEqual(self.decide()["state"], "clore_acknowledged")
        return issue_receipt(self.telegram.db, nonce=self.nonce,
                             private_key_raw=self.private, now=NOW)

    def record(self, receipt):
        return record_verified_consent(
            self.guard, receipt=receipt, trusted_public_key_raw=self.public,
            reservation_id=self.reservation, now=NOW, timer_check=True
        )

    def test_signed_exact_consent_is_not_financial_grant(self):
        receipt = self.signed()
        self.assertEqual(receipt["statement"]["terms_sha256"], self.proposal["digest"])
        self.assertEqual(receipt["statement"]["message_id"], 77)
        self.assertEqual(verify_receipt(
            receipt, trusted_public_key_raw=self.public, now=NOW)["nonce"], self.nonce)
        verified = self.record(receipt)
        self.assertTrue(verified["consent_recorded"])
        self.assertFalse(verified["rental_permitted"])
        self.assertFalse(verified["provider_mutation"])
        self.assertEqual(self.guard.execute("SELECT state FROM clore_consent_receipts"
                                            ).fetchone()[0], "verified_only")
        self.assertEqual(self.guard.execute(
            "SELECT COUNT(*) FROM clore_cancel_leases").fetchone()[0], 0)
        self.assertEqual(self.guard.execute(
            "SELECT phase FROM clore_preorders").fetchone()[0], "reserved")

    def test_replay_is_blocked_on_same_database_and_after_reopen(self):
        receipt = self.signed()
        self.record(receipt)
        with self.assertRaisesRegex(ConsentError, "consent_receipt_already_used"):
            self.record(receipt)
        with sqlite3.connect(self.path/"finance.sqlite3", isolation_level=None) as newdb:
            with self.assertRaisesRegex(ConsentError, "consent_receipt_already_used"):
                record_verified_consent(
                    newdb, receipt=receipt, trusted_public_key_raw=self.public,
                    reservation_id=self.reservation, now=NOW, timer_check=True)
        self.assertEqual(self.guard.execute(
            "SELECT COUNT(*) FROM clore_consent_receipts").fetchone()[0], 1)

    def test_rejected_and_undelivered_offers_cannot_be_signed(self):
        with self.assertRaisesRegex(ConsentError, "consent_not_current_or_acknowledged"):
            issue_receipt(self.telegram.db, nonce=self.nonce,
                          private_key_raw=self.private, now=NOW)
        self.decide("reject")
        with self.assertRaisesRegex(ConsentError, "consent_not_current_or_acknowledged"):
            issue_receipt(self.telegram.db, nonce=self.nonce,
                          private_key_raw=self.private, now=NOW)
        self.assertEqual(self.guard.execute(
            "SELECT COUNT(*) FROM clore_consent_receipts").fetchone()[0], 0)

    def test_public_key_cannot_sign_and_wrong_key_is_rejected(self):
        receipt = self.signed()
        with self.assertRaisesRegex(ConsentError, "bad_consent_signature|untrusted_signing_key"):
            wrong = Ed25519PrivateKey.generate().public_key().public_bytes(
                Encoding.Raw, PublicFormat.Raw)
            verify_receipt(receipt, trusted_public_key_raw=wrong, now=NOW)
        with self.assertRaisesRegex(ConsentError, "invalid_signing_key"):
            issue_receipt(self.telegram.db, nonce=self.nonce,
                          private_key_raw=b"", now=NOW)

    def test_tampered_message_budget_expiry_audience_and_signature_fail(self):
        original = self.signed()
        variants = []
        for field, value in (("message_id", 999), ("expires_at", NOW+1200),
                             ("audience", "other-account"),
                             ("terms_sha256", "f"*64)):
            bad = copy.deepcopy(original)
            bad["statement"][field] = value
            variants.append(bad)
        bad = copy.deepcopy(original)
        bad["signature"] = "AAAA"
        variants.append(bad)
        bad = copy.deepcopy(original)
        bad["key_id"] = "f"*64
        variants.append(bad)
        for receipt in variants:
            with self.subTest(receipt=receipt), self.assertRaises(ConsentError):
                self.record(receipt)
        self.assertEqual(self.guard.execute(
            "SELECT COUNT(*) FROM clore_consent_receipts").fetchone()[0],0)

    def test_finance_reservation_mismatch_is_rejected(self):
        receipt = self.signed()
        self.guard.execute("""UPDATE clore_preorders
                     SET terms_sha256=?""", ("f"*64,))
        with self.assertRaisesRegex(ConsentError, "unapproved_or_stale_reservation"):
            self.record(receipt)
        self.assertEqual(self.guard.execute(
            "SELECT COUNT(*) FROM clore_consent_receipts").fetchone()[0], 0)

    def test_expired_quote_and_receipt_cannot_grant(self):
        receipt = self.signed()
        with self.assertRaisesRegex(ConsentError,"consent_expired_or_wrong_audience"):
            verify_receipt(receipt, trusted_public_key_raw=self.public, now=NOW+200)
        self.guard.execute("UPDATE clore_cancel_heartbeat SET completed_at=?", (NOW+130,))
        with self.assertRaisesRegex(ConsentError,"consent_expired_or_wrong_audience"):
            record_verified_consent(
                self.guard, receipt=receipt, trusted_public_key_raw=self.public,
                reservation_id=self.reservation, now=NOW+130, timer_check=True
            )

    def test_unhealthy_watchdog_blocks_receipt_import(self):
        receipt = self.signed()
        with self.assertRaisesRegex(Exception, "independent_cancel_timer_inactive"):
            record_verified_consent(
                self.guard, receipt=receipt, trusted_public_key_raw=self.public,
                reservation_id=self.reservation, now=NOW, timer_check=False)
        self.guard.execute("DELETE FROM clore_cancel_heartbeat")
        with self.assertRaisesRegex(Exception, "independent_cancel_supervisor_unhealthy"):
            self.record(receipt)

    def test_cannot_open_another_users_database_to_record(self):
        receipt = self.signed()
        wrong_reservation = "0"*32
        with self.assertRaisesRegex(ConsentError,"unreserved_clore_terms"):
            record_verified_consent(
                self.guard, receipt=receipt, trusted_public_key_raw=self.public,
                reservation_id=wrong_reservation, now=NOW, timer_check=True)
        self.assertEqual(self.guard.execute(
            "SELECT COUNT(*) FROM clore_consent_receipts").fetchone()[0], 0)

    def test_tampered_telegram_database_cannot_issue_a_signed_receipt(self):
        self.decide()
        self.telegram.db.execute("""UPDATE clore_telegram_offers
              SET payload='{}' WHERE nonce=?""", (self.nonce,))
        with self.assertRaisesRegex(ConsentError, "consent_payload_tampered"):
            issue_receipt(self.telegram.db, nonce=self.nonce,
                          private_key_raw=self.private, now=NOW)
        self.assertEqual(self.guard.execute(
            "SELECT COUNT(*) FROM clore_consent_receipts").fetchone()[0], 0)

if __name__ == "__main__":
    unittest.main()
