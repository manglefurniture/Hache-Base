"""Zero-spend pre-order reserve/reconciliation tests. No real provider requests."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from clore_cancel_guard import db_open, GuardError, arm
from clore_preorder import reserve, evaluate_candidate, init_schema, inventory_baseline

NOW = 1800000000
IMAGE = "ghcr.io/manglefurniture/prl-miner@sha256:" + "a"*64


def terms(**kw):
    obj = {"server_id": 456, "currency": "USD-Blockchain",
           "gpu_descriptor": "1x NVIDIA GeForce RTX 5090", "gpu_variant": "desktop",
           "gpu_variant_verified": True, "image": IMAGE,
           "daily_bid_usd": "12", "max_total_usd": "1",
           "creation_fee_usd": "0.10", "max_minutes": 60,
           "quote_observed_at": datetime.fromtimestamp(NOW-20, timezone.utc).isoformat()}
    obj.update(kw)
    return obj


def order(oid=100, **kw):
    row = {"id": oid, "si": 456, "currency": "USD-Blockchain",
           "spot": True, "expired": False, "ct": NOW + 1, "image": IMAGE,
           "price": 12, "creation_fee": 0.10, "fee": 5, "spend": 0,
           "specs": {"gpu": "1x NVIDIA GeForce RTX 5090"}}
    row.update(kw)
    return row


class Provider:
    def __init__(self, orders=None, limit=10):
        self.orders = [] if orders is None else orders
        self.limit = limit
        self.calls = []
    def inventory(self):
        self.calls.append("GET my_orders")
        return {"limit": self.limit, "orders": self.orders}


class PreorderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.file = Path(self.tmp.name) / "guard.sqlite3"
        self.db = db_open(self.file)
        self.db.execute("INSERT INTO clore_cancel_heartbeat VALUES(1,?)", (NOW - 10,))
        self.provider = Provider([order(90, ct=NOW-300, expired=True)])
    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()
    def hold(self, **options):
        args = dict(terms=terms(), api=self.provider, now=NOW, timer_check=True)
        args.update(options)
        return reserve(self.db, **args)

    def test_preflight_is_durable_and_never_creates(self):
        receipt = self.hold()
        self.assertFalse(receipt["rental_permitted"])
        self.assertFalse(receipt["provider_mutation"])
        self.assertEqual(self.provider.calls, ["GET my_orders"])
        self.assertEqual(receipt["baseline_count"], 1)
        self.assertEqual(len(receipt["reservation_id"]), 32)
        reopened = sqlite3.connect(self.file)
        self.assertEqual(reopened.execute("SELECT phase,outcome FROM clore_preorders").fetchone(),
                         ("reserved", "create_not_enabled"))
        reopened.close()

    def test_active_lease_and_duplicate_hold_block_rental_plans(self):
        self.hold()
        with self.assertRaisesRegex(GuardError, "existing_preorder_obligation"):
            self.hold()
        self.db.execute("UPDATE clore_preorders SET phase='abandoned'")
        self.db.execute("""INSERT INTO clore_cancel_leases
            (order_id,server_id,daily_bid_usd,budget_usd,creation_fee_usd,max_minutes,created_at,cutoff_at,phase)
            VALUES(42,456,'12','1','0.1',60,1800000000,1800003600,'armed')""")
        with self.assertRaisesRegex(GuardError, "active_clore_obligation"):
            self.hold()

    def test_healthy_independent_timer_required(self):
        with self.assertRaisesRegex(GuardError, "independent_cancel_timer_inactive"):
            self.hold(timer_check=False)
        self.db.execute("DELETE FROM clore_cancel_heartbeat")
        with self.assertRaisesRegex(GuardError, "independent_cancel_supervisor_unhealthy"):
            self.hold()

    def test_reject_wrong_currency_unverified_gpu_image_and_stale_quote(self):
        bad = [terms(currency="bitcoin"), terms(currency="usdt"),
               terms(gpu_variant="unverified"), terms(gpu_variant_verified=False),
               terms(image="ghcr.io/manglefurniture/prl-miner:latest"),
               terms(quote_observed_at="2020-01-01T00:00:00Z"),
               terms(max_minutes=1), terms(max_total_usd="0.2"),
               terms(daily_bid_usd="NaN"), terms(server_id=True)]
        for candidate in bad:
            with self.subTest(candidate=candidate), self.assertRaises(GuardError):
                self.hold(terms=candidate)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM sqlite_master "
            "WHERE name='clore_preorders'").fetchone()[0], 0)

    def test_baseline_must_be_unambiguous_and_not_saturated(self):
        for rows, limit in [([order(100),order(100)], 5),
                            ([order(100)], 1),
                            ([{"id": True}], 4),
                            ([{"id": 0}], 4)]:
            p=Provider(rows,limit)
            with self.subTest(rows=rows), self.assertRaises(GuardError):
                self.hold(api=p)

    def test_new_exact_candidate_does_not_automatically_bind_or_rent(self):
        receipt=self.hold()
        self.provider.orders=[order(90,ct=NOW-300,expired=True),order(222)]
        result=evaluate_candidate(self.db, reservation_id=receipt["reservation_id"],
                                  api=self.provider,now=NOW+3)
        self.assertEqual(result["status"],"candidate_unbound")
        self.assertEqual(result["candidate_order_id"],222)
        self.assertFalse(result["rental_permitted"])
        self.assertEqual(self.db.execute("SELECT phase FROM clore_preorders").fetchone()[0],"reserved")
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM clore_cancel_leases").fetchone()[0],0)
        self.assertEqual(self.provider.calls,["GET my_orders","GET my_orders"])

    def test_reconcile_order_that_fills_the_final_account_slot(self):
        self.provider.limit = 1
        self.assertEqual(len([o for o in self.provider.orders if not o["expired"]]), 0)
        receipt = self.hold()
        self.provider.orders.append(order(222))
        self.assertEqual(
            evaluate_candidate(self.db, reservation_id=receipt["reservation_id"],
                               api=self.provider, now=NOW+3)["status"],
            "candidate_unbound")
        # A new reservation would be blocked while all capacity is consumed.
        with self.assertRaisesRegex(GuardError, "inventory_capacity_or_completeness_uncertain"):
            inventory_baseline(self.provider)

    def test_missing_ambiguous_or_mismatched_candidates_never_bind(self):
        receipt=self.hold()
        rid=receipt["reservation_id"]
        examples=[
            ([order(90,ct=NOW-300,expired=True)],"not_found"),
            ([order(90,ct=NOW-300,expired=True),order(111),order(112)],"ambiguous"),
            ([order(222,currency="bitcoin")],"identity_mismatch"),
            ([order(222,image="other/image@sha256:"+"b"*64)],"identity_mismatch"),
            ([order(222,ct=NOW-100)],"identity_mismatch"),
            ([order(222,specs={"gpu":"8x RTX 5090"})],"identity_mismatch"),
            ([order(222,price=99)],"price_or_fee_mismatch"),
            ([order(222,fee=10)],"price_or_fee_mismatch"),
            ([order(222,spend=1)],"price_or_fee_mismatch"),
        ]
        for rows, expected in examples:
            self.provider.orders=rows
            with self.subTest(expected=expected, rows=rows):
                result=evaluate_candidate(self.db,reservation_id=rid,api=self.provider,now=NOW+3)
                self.assertEqual(result["status"], expected)
                self.assertFalse(result["rental_permitted"])
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM clore_cancel_leases").fetchone()[0],0)

    def test_tampering_blocks_reconciliation(self):
        receipt=self.hold()
        self.db.execute("UPDATE clore_preorders SET terms_json='{}'")
        with self.assertRaisesRegex(GuardError,"preorder_payload_tampered"):
            evaluate_candidate(self.db,reservation_id=receipt["reservation_id"],api=self.provider,now=NOW+3)

    def test_manual_arm_blocked_by_open_preorder(self):
        self.hold()
        row={"id":999,"si":456,"ct":NOW,"spot":True,"expired":False,
             "currency":"USD-Blockchain","price":12,"creation_fee":0.10,
             "fee":5,"spend":0}
        with self.assertRaisesRegex(GuardError,"existing_preorder_obligation"):
            arm(self.db,order_id=999,server_id=456,daily_bid_usd="12",
                budget_usd="1",creation_fee_usd="0.1",max_minutes=60,
                created_at=NOW,provider_order=row,now=NOW,
                timer_check=lambda:True)

    def test_reserved_state_persists_after_quote_timeout(self):
        receipt=self.hold()
        result=evaluate_candidate(self.db,reservation_id=receipt["reservation_id"],
                                  api=self.provider,now=NOW+1000)
        self.assertEqual(result["status"],"not_found")
        self.assertEqual(self.db.execute("SELECT phase FROM clore_preorders").fetchone()[0],"reserved")
        with self.assertRaisesRegex(GuardError,"existing_preorder_obligation"):
            self.hold()

if __name__ == "__main__":
    unittest.main()
