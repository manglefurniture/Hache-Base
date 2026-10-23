"""No-spend Clore watchdog tests for an uncertain create response."""
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from clore_cancel_guard import db_open, tick, GuardError
from clore_preorder import reserve
from clore_pending_recovery import pending

NOW = 1800000000
IMAGE = "ghcr.io/manglefurniture/prl-miner@sha256:"+"a"*64


def terms():
    return {"server_id": 456, "currency": "USD-Blockchain",
            "gpu_descriptor": "1x NVIDIA GeForce RTX 5090",
            "gpu_variant": "desktop", "gpu_variant_verified": True,
            "image": IMAGE, "daily_bid_usd": "12",
            "max_total_usd": "1", "creation_fee_usd": "0.10",
            "max_minutes": 60,
            "quote_observed_at": datetime.fromtimestamp(NOW-1,timezone.utc).isoformat()}


def order(oid=20, **kwargs):
    result={"id":oid,"si":456,"spot":True,"expired":False,
            "currency":"USD-Blockchain","ct":NOW+1,"image":IMAGE,
            "specs":{"gpu":"1x NVIDIA GeForce RTX 5090"},
            "price":12,"fee":5,"creation_fee":0.1,"spend":0}
    result.update(kwargs)
    return result


class FakeProvider:
    def __init__(self):
        self.records=[]
        self.gets=0
        self.cancels=[]
        self.fail=False
    def inventory(self):
        self.gets+=1
        if self.fail:
            raise GuardError("provider_request_failed")
        return {"limit":10,"orders":self.records}
    def orders(self):
        self.gets+=1
        if self.fail:
            raise GuardError("provider_request_failed")
        return self.records
    def cancel(self, order_id):
        self.cancels.append(order_id)


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.dir=tempfile.TemporaryDirectory()
        self.db=db_open(Path(self.dir.name)/"cancel.sqlite3")
        self.db.execute("INSERT INTO clore_cancel_heartbeat(id,completed_at) VALUES(1,?)",(NOW-1,))
        self.api=FakeProvider()
    def tearDown(self):
        self.db.close()
        self.dir.cleanup()
    def prepare(self,outcome="create_response_unknown"):
        record=reserve(self.db,terms=terms(),api=self.api,now=NOW,timer_check=True)
        self.db.execute("UPDATE clore_preorders SET phase='uncertain',outcome=?", (outcome,))
        return record["reservation_id"]
    def check(self, expected):
        with self.assertRaisesRegex(GuardError,"possible_unprotected_clore_order"):
            tick(self.db,self.api,now=NOW+5,delay=lambda _:None)
        row=self.db.execute("SELECT status,candidate_order_id FROM clore_pending_recovery").fetchone()
        self.assertEqual(row[0],expected)
        self.assertEqual(self.db.execute("SELECT phase FROM clore_preorders").fetchone()[0],"uncertain")
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM clore_cancel_leases").fetchone()[0],0)
        self.assertEqual(self.api.cancels,[])
        return row

    def test_idle_unmodified_without_unknown_order(self):
        response=tick(self.db,self.api,now=NOW+1,delay=lambda _:None)
        self.assertEqual(response["status"],"idle")
        self.assertEqual(self.api.gets,1)
        self.assertEqual(pending(self.db),[])

    def test_unknown_create_timeout_remains_blocking(self):
        self.prepare()
        self.check("not_found")
        self.assertEqual(self.api.gets,2)
        with self.assertRaisesRegex(GuardError,"existing_preorder_obligation"):
            reserve(self.db,terms=terms(),api=self.api,now=NOW+6,timer_check=True)

    def test_candidate_exact_is_not_cancelled_or_bound(self):
        self.prepare()
        self.api.records=[order(99)]
        evidence=self.check("candidate_unbound")
        self.assertEqual(evidence[1],99)
        with self.assertRaisesRegex(GuardError,"possible_unprotected_clore_order"):
            tick(self.db,self.api,now=NOW+35,delay=lambda _:None)
        self.assertEqual(self.db.execute(
            "SELECT candidate_order_id FROM clore_pending_recovery").fetchone()[0],99)

    def test_concurrent_order_is_ambiguous(self):
        self.prepare()
        self.api.records=[order(99),order(101,si=902)]
        self.check("ambiguous")

    def test_different_server_must_not_be_cancelled(self):
        self.prepare()
        self.api.records=[order(11,si=999)]
        self.check("unrelated_new_order")

    def test_wrong_image_currency_and_cost_not_bound(self):
        cases=[(dict(image="other/image@sha256:"+"b"*64),"identity_mismatch"),
               (dict(currency="bitcoin"),"identity_mismatch"),
               (dict(price=99),"price_or_fee_mismatch"),
               (dict(spend="0.9"),"price_or_fee_mismatch")]
        for changes, status in cases:
            with self.subTest(changes=changes):
                self.db.execute("DELETE FROM clore_pending_recovery")
                self.api.records=[order(88,**changes)]
                if not self.db.execute("SELECT 1 FROM clore_preorders").fetchone():
                    self.prepare()
                self.check(status)
        self.assertEqual(self.api.cancels,[])

    def test_untrusted_journal_status_is_rejected(self):
        self.prepare(outcome="create_not_enabled")
        with self.assertRaisesRegex(GuardError,"untrusted_uncertain_preorder_state"):
            tick(self.db,self.api,now=NOW+5,delay=lambda _:None)
        self.assertEqual(self.api.cancels,[])

    def test_failed_provider_get_does_not_claim_safe_heartbeat(self):
        self.prepare()
        old=self.db.execute("SELECT completed_at FROM clore_cancel_heartbeat").fetchone()[0]
        self.api.fail=True
        with self.assertRaisesRegex(GuardError,"provider_request_failed"):
            tick(self.db,self.api,now=NOW+5,delay=lambda _:None)
        self.assertEqual(self.db.execute(
            "SELECT completed_at FROM clore_cancel_heartbeat").fetchone()[0],old)
        self.assertEqual(self.api.cancels,[])


if __name__ == "__main__":
    unittest.main()
