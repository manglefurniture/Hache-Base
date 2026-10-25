"""Clore pre-submit write-ahead and offline decisions, zero provider spending."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sqlite3
import tempfile
import unittest

from clore_cancel_guard import db_open, GuardError, tick
from clore_create_journal import init_schema, stage_once, record_unknown, status
from clore_consent_attestation import issue_receipt, record_verified_consent, init_ledger_schema
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, PublicFormat, NoEncryption
from clore_offline_simulation import SimulatedClore, simulate_once
from clore_preorder import reserve
from telegram_proposals import ProposalStore

NOW=1800000000
IMAGE="ghcr.io/manglefurniture/prl-miner@sha256:"+"a"*64


def terms(**updates):
    t={"server_id":456, "currency":"USD-Blockchain",
       "gpu_descriptor":"1x NVIDIA GeForce RTX 5090", "gpu_variant":"desktop",
       "gpu_variant_verified":True, "image":IMAGE, "daily_bid_usd":"12",
       "max_total_usd":"1", "creation_fee_usd":"0.1", "max_minutes":60,
       "quote_observed_at":datetime.fromtimestamp(NOW-10,timezone.utc).isoformat()}
    t.update(updates)
    return t


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.file=Path(self.temp.name)/"guard.sqlite3"
        self.db=db_open(self.file)
        init_schema(self.db)
        self.db.execute("INSERT INTO clore_cancel_heartbeat(id,completed_at) VALUES(1,?)",(NOW,))
        self.fake=SimulatedClore()
        self.telegram=ProposalStore(str(Path(self.temp.name)/"telegram.sqlite3"))
        key=Ed25519PrivateKey.generate()
        self.private=key.private_bytes(Encoding.Raw,PrivateFormat.Raw,NoEncryption())
        self.public=key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
        init_ledger_schema(self.db)

    def tearDown(self):
        self.telegram.close()
        self.db.close()
        self.temp.cleanup()

    def hold(self):
        return reserve(self.db,terms=terms(),api=self.fake,now=NOW,timer_check=True)

    def staged(self):
        r=self.hold()
        digest=self.db.execute(
            "SELECT terms_sha256 FROM clore_preorders WHERE reservation_id=?",
            (r["reservation_id"],)).fetchone()[0]
        nonce=self.approve()
        receipt=issue_receipt(self.telegram.db,nonce=nonce,
                              private_key_raw=self.private,now=NOW)
        record_verified_consent(
            self.db,receipt=receipt,trusted_public_key_raw=self.public,
            reservation_id=r["reservation_id"],now=NOW,timer_check=True)
        stage_once(self.db,reservation_id=r["reservation_id"],
                   expected_digest=digest,now=NOW,timer_check=True)
        return r["reservation_id"],digest

    def approve(self,approve=True):
        stamp=datetime.fromtimestamp(NOW,timezone.utc)
        p=self.telegram.prepare_clore(terms(),now=stamp)
        nonce=p["proposal_id"]
        self.telegram.mark_clore_notified(nonce,77,NOW)
        if approve:
            event={"update_id":1,"callback_query":{"id":"owner",
                   "from":{"id":123},"message":{"message_id":77,
                   "chat":{"id":123,"type":"private"}},
                   "data":"clore-accept:"+nonce}}
            result=self.telegram.process_update(event,123,123,NOW)
            self.assertEqual(result["state"],"clore_acknowledged")
        return nonce

    def test_unsigned_reservation_cannot_stage_any_risk_marker(self):
        r=self.hold()
        digest=self.db.execute("SELECT terms_sha256 FROM clore_preorders").fetchone()[0]
        with self.assertRaisesRegex(GuardError,"verified_signed_consent_required"):
            stage_once(self.db,reservation_id=r["reservation_id"],
                       expected_digest=digest,now=NOW,timer_check=True)
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM clore_create_attempts").fetchone()[0],0)

    def test_prepost_journal_atomic_and_single_use_after_restart(self):
        rid,digest=self.staged()
        self.assertEqual(status(self.db,rid)["status"],"create_submitted_once")
        self.assertEqual(tuple(self.db.execute(
            "SELECT phase,outcome FROM clore_preorders").fetchone()),
            ("uncertain","create_submitted_once"))
        reopened=sqlite3.connect(self.file,isolation_level=None)
        with self.assertRaisesRegex(GuardError,"create_already_staged_or_reservation_invalid"):
            stage_once(reopened,reservation_id=rid,expected_digest=digest,now=NOW,
                       timer_check=True)
        reopened.close()
        self.assertEqual(self.fake.create_count,0)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM clore_cancel_leases").fetchone()[0],0)

    def test_mismatched_digest_or_expired_quote_cannot_stage(self):
        r=self.hold()
        rid=r["reservation_id"]
        with self.assertRaisesRegex(GuardError,"reservation_terms_mismatch"):
            stage_once(self.db,reservation_id=rid,expected_digest="f"*64,
                       now=NOW,timer_check=True)
        self.assertEqual(status(self.db,rid)["status"],"not_staged")
        digest=self.db.execute("SELECT terms_sha256 FROM clore_preorders").fetchone()[0]
        self.db.execute("UPDATE clore_cancel_heartbeat SET completed_at=?",(NOW+121,))
        with self.assertRaisesRegex(GuardError,"reservation_window_closed"):
            stage_once(self.db,reservation_id=rid,expected_digest=digest,
                       now=NOW+121,timer_check=True)
        self.assertEqual(self.db.execute("SELECT phase FROM clore_preorders").fetchone()[0],"reserved")

    def test_bad_supervisor_heartbeat_and_existing_lease_fail_closed(self):
        r=self.hold()
        rid=r["reservation_id"]
        digest=self.db.execute("SELECT terms_sha256 FROM clore_preorders").fetchone()[0]
        with self.assertRaisesRegex(GuardError,"independent_cancel_timer_inactive"):
            stage_once(self.db,reservation_id=rid,expected_digest=digest,now=NOW,timer_check=False)
        self.db.execute("DELETE FROM clore_cancel_heartbeat")
        with self.assertRaisesRegex(GuardError,"independent_cancel_supervisor_unhealthy"):
            stage_once(self.db,reservation_id=rid,expected_digest=digest,now=NOW,timer_check=True)
        self.assertEqual(status(self.db,rid)["status"],"not_staged")

    def test_unknown_response_is_permanent_and_alerted_by_watchdog(self):
        rid,_=self.staged()
        record_unknown(self.db,reservation_id=rid,now=NOW+1)
        record_unknown(self.db,reservation_id=rid,now=NOW+2)
        self.assertEqual(status(self.db,rid)["status"],"create_response_unknown")
        self.assertEqual(tuple(self.db.execute(
            "SELECT phase,outcome FROM clore_preorders").fetchone()),
            ("uncertain","create_response_unknown"))
        with self.assertRaisesRegex(GuardError,"possible_unprotected_clore_order"):
            tick(self.db,self.fake,now=NOW+3,delay=lambda _:None)
        self.assertEqual(self.fake.create_count,0)

    def test_offline_success_is_unbound_even_with_exact_candidate(self):
        nonce=self.approve()
        result=simulate_once(private_key_raw=self.private,
                          trusted_public_key_raw=self.public,telegram_db=self.telegram.db,guard_db=self.db,
                             nonce=nonce,provider=self.fake,now=NOW)
        self.assertEqual(result["candidate_status"],"candidate_unbound")
        self.assertFalse(result["rental_permitted"])
        self.assertEqual(result["live_provider_mutations"],0)
        self.assertEqual(self.fake.create_count,1)
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM clore_cancel_leases").fetchone()[0],0)
        self.assertEqual(tuple(self.db.execute(
            "SELECT phase,outcome FROM clore_preorders").fetchone()),
            ("uncertain","create_response_unknown"))
        with self.assertRaisesRegex(GuardError,"existing_preorder_obligation"):
            simulate_once(private_key_raw=self.private,
                          trusted_public_key_raw=self.public,telegram_db=self.telegram.db,guard_db=self.db,
                          nonce=nonce,provider=self.fake,now=NOW)
        self.assertEqual(self.fake.create_count,1)

    def test_offline_timeout_after_accepting_order_leaves_risk_unbound(self):
        self.fake=SimulatedClore("timeout_after_create")
        receipt=simulate_once(private_key_raw=self.private,
                          trusted_public_key_raw=self.public,telegram_db=self.telegram.db,guard_db=self.db,
            nonce=self.approve(),provider=self.fake,now=NOW)
        self.assertEqual(receipt["candidate_status"],"candidate_unbound")
        self.assertEqual(self.fake.create_count,1)
        with self.assertRaisesRegex(GuardError,"possible_unprotected_clore_order"):
            tick(self.db,self.fake,now=NOW+5,delay=lambda _:None)

    def test_offline_timeout_without_order_remains_uncertain(self):
        self.fake=SimulatedClore("timeout_before_create")
        receipt=simulate_once(private_key_raw=self.private,
                          trusted_public_key_raw=self.public,telegram_db=self.telegram.db,guard_db=self.db,
            nonce=self.approve(),provider=self.fake,now=NOW)
        self.assertEqual(receipt["candidate_status"],"not_found")
        self.assertEqual(self.db.execute(
            "SELECT phase FROM clore_preorders").fetchone()[0],"uncertain")
        self.assertEqual(len(self.fake.orders),0)

    def test_rejected_tampered_or_expired_approval_never_calls_create(self):
        nonce=self.approve(False)
        with self.assertRaisesRegex(GuardError,"untrusted_or_expired_telegram_decision"):
            simulate_once(private_key_raw=self.private,
                          trusted_public_key_raw=self.public,telegram_db=self.telegram.db,guard_db=self.db,
                          nonce=nonce,provider=self.fake,now=NOW)
        self.assertEqual(self.fake.create_count,0)
        self.telegram.db.execute("UPDATE clore_telegram_offers SET state='acknowledged',payload='{}'")
        with self.assertRaisesRegex(GuardError,"untrusted_or_expired_telegram_decision"):
            simulate_once(private_key_raw=self.private,
                          trusted_public_key_raw=self.public,telegram_db=self.telegram.db,guard_db=self.db,
                          nonce=nonce,provider=self.fake,now=NOW)
        self.assertEqual(self.fake.create_count,0)

    def test_disallow_real_provider_type_and_expired_decision(self):
        nonce=self.approve()
        class ProviderProxy:
            def inventory(self):
                raise AssertionError("real external provider must never be touched")
        with self.assertRaisesRegex(GuardError,"offline_simulator_only"):
            simulate_once(private_key_raw=self.private,
                          trusted_public_key_raw=self.public,telegram_db=self.telegram.db,guard_db=self.db,
                          nonce=nonce,provider=ProviderProxy(),now=NOW)
        with self.assertRaisesRegex(GuardError,"untrusted_or_expired_telegram_decision"):
            simulate_once(private_key_raw=self.private,
                          trusted_public_key_raw=self.public,telegram_db=self.telegram.db,guard_db=self.db,
                          nonce=nonce,provider=self.fake,now=NOW+121)
        self.assertEqual(self.fake.create_count,0)

if __name__=="__main__":
    unittest.main()
