"""Offline tests; never access Clore or its credentials."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from clore_cancel_guard import (arm, db_open, tick, GuardError, CloreAPI, credential)

class FakeClore:
    def __init__(self, entries=None, *, fail_get=False, fail_cancel=False):
        self.entries = [] if entries is None else entries
        self.fail_get = fail_get
        self.fail_cancel = fail_cancel
        self.cancels = []
        self.gets = 0
    def orders(self):
        self.gets += 1
        if self.fail_get:
            raise GuardError("provider_request_failed")
        return self.entries
    def cancel(self, oid):
        self.cancels.append(oid)
        if self.fail_cancel:
            raise GuardError("provider_request_failed")

class CloreWatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = db_open(Path(self.tmp.name)/"leases.sqlite")
        self.db.execute("INSERT INTO clore_cancel_heartbeat(id,completed_at) VALUES(1,995)")
    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()
    def arm(self, **opts):
        inputs = dict(order_id=456, server_id=121322, daily_bid_usd="10",
                      budget_usd="1", creation_fee_usd="0",
                      max_minutes=60, created_at=1000, now=1000,
                      timer_check=lambda:True)
        inputs.update(opts)
        return arm(self.db, **inputs)
    def order(self, expired=False, si=121322):
        return {"id":456, "si":si, "expired":expired}
    def run_tick(self, api, now):
        return tick(self.db, api, now=now, delay=lambda _:None)
    def phase(self):
        row=self.db.execute("SELECT phase,last_outcome,last_attempt FROM clore_cancel_leases").fetchone()
        return tuple(row) if row else None
    def test_arms_but_never_creates_or_cancels_early(self):
        result=self.arm()
        self.assertEqual(result["state"], "armed")
        self.assertEqual(result["cutoff_at"], 1000+60*60)
        p=FakeClore([self.order()])
        self.assertEqual(self.run_tick(p, 2000)["status"],"watching")
        self.assertEqual(p.cancels, [])
    def test_budget_cutoff_precedes_time_limit(self):
        r=self.arm(budget_usd="0.2", max_minutes=120)
        self.assertLess(r["cutoff_at"], 1000+120*60)
        self.assertGreater(r["cutoff_at"], 1000)
    def test_actual_creation_fee_reduces_remaining_budget(self):
        base=self.arm(budget_usd="0.3", max_minutes=120)
        self.db.execute("DELETE FROM clore_cancel_leases")
        with_fee=self.arm(budget_usd="0.3", creation_fee_usd="0.10", max_minutes=120)
        self.assertLess(with_fee["cutoff_at"],base["cutoff_at"])
    def test_late_registration_is_rejected_before_timer_interval(self):
        self.db.execute("UPDATE clore_cancel_heartbeat SET completed_at=4565")
        with self.assertRaisesRegex(GuardError,"insufficient_time_for_independent_cancel_cycle"):
            self.arm(now=4565)
    def test_creation_fee_must_fit_in_authorized_total(self):
        with self.assertRaisesRegex(GuardError,"creation_fee_exceeds_budget"):
            self.arm(budget_usd="0.1", creation_fee_usd="0.1")
        with self.assertRaisesRegex(GuardError,"invalid_creation_fee"):
            self.arm(creation_fee_usd="-2")
    def test_deadline_cancel_needs_separate_provider_confirmation(self):
        r=self.arm()
        p=FakeClore([self.order()])
        self.assertEqual(self.run_tick(p, r["cutoff_at"])["status"], "cancel_submitted_unverified")
        self.assertEqual(p.cancels, [456])
        self.assertEqual(self.phase()[0], "armed")
        p.entries=[self.order(expired=True)]
        self.assertEqual(self.run_tick(p, r["cutoff_at"]+31)["status"], "verified_closed")
        self.assertEqual(self.phase()[0], "closed")
        self.assertEqual(p.cancels, [456])
    def test_failed_cancel_retries_and_does_not_claim_success(self):
        r=self.arm()
        p=FakeClore([self.order()],fail_cancel=True)
        with self.assertRaisesRegex(GuardError,"cancel_failed_retry_next_tick"):
            self.run_tick(p, r["cutoff_at"])
        self.assertEqual(self.phase()[0], "armed")
        p.fail_cancel=False
        self.run_tick(p, r["cutoff_at"]+30)
        self.assertEqual(p.cancels,[456,456])
    def test_failed_inventory_attempts_cancel_if_overdue(self):
        r=self.arm()
        p=FakeClore(fail_get=True)
        self.assertEqual(self.run_tick(p, r["cutoff_at"])["status"], "cancel_submitted_unverified")
        self.assertEqual(p.cancels,[456])
        self.assertEqual(self.phase()[0], "armed")
    def test_price_or_overclock_change_triggers_early_cancel(self):
        self.arm()
        for change in ({"price": 11}, {"price":"NaN"}, {"oc_price": 0.2}):
            with self.subTest(change=change):
                p=FakeClore([{**self.order(), **change}])
                self.assertEqual(self.run_tick(p, 1100)["status"],"cancel_submitted_unverified")
                self.assertEqual(p.cancels, [456])
                self.assertEqual(self.phase()[0],"armed")
    def test_missing_history_is_not_proof_of_cancel(self):
        r=self.arm()
        p=FakeClore([])
        self.assertEqual(self.run_tick(p,1100)["status"],"order_not_found")
        self.assertEqual(self.phase()[0], "armed")
        self.run_tick(p, r["cutoff_at"])
        self.assertEqual(p.cancels,[456])
        self.assertEqual(self.phase()[0], "armed")
    def test_mismatched_identity_never_cancels_unknown_server(self):
        r=self.arm()
        p=FakeClore([self.order(si=9)])
        with self.assertRaisesRegex(GuardError,"order_server_identity_mismatch"):
            self.run_tick(p, r["cutoff_at"])
        self.assertEqual(p.cancels,[])
        self.assertEqual(self.phase()[0],"armed")
    def test_already_expired_closes_without_post(self):
        self.arm()
        p=FakeClore([self.order(expired=True)])
        self.assertEqual(self.run_tick(p, 1005)["status"],"verified_closed")
        self.assertFalse(p.cancels)
    def test_one_active_order_at_a_time(self):
        self.arm()
        with self.assertRaisesRegex(GuardError,"existing_armed_order"):
            self.arm(order_id=789)
    def test_no_arm_without_healthy_independent_supervisor(self):
        with self.assertRaisesRegex(GuardError,"independent_cancel_timer_inactive"):
            self.arm(timer_check=lambda:False)
        self.db.execute("DELETE FROM clore_cancel_heartbeat")
        with self.assertRaisesRegex(GuardError,"independent_cancel_supervisor_unhealthy"):
            self.arm()
    def test_idle_tick_requires_provider_success_and_refreshes_heartbeat(self):
        p=FakeClore([])
        self.assertEqual(self.run_tick(p,1005)["status"],"idle")
        self.assertEqual(self.db.execute(
            "SELECT completed_at FROM clore_cancel_heartbeat").fetchone()[0],1005)
        with self.assertRaisesRegex(GuardError,"provider_request_failed"):
            self.run_tick(FakeClore(fail_get=True),1006)
        self.assertEqual(self.db.execute(
            "SELECT completed_at FROM clore_cancel_heartbeat").fetchone()[0],1005)
    def test_bad_inputs_rejected(self):
        for opts in ({"order_id":True},{"server_id":0},{"max_minutes":0},
                     {"max_minutes":1441},{"created_at":1100},
                     {"daily_bid_usd":"NaN"},{"budget_usd":"-1"},{"creation_fee_usd":"NaN"},
                     {"budget_usd":"0.00000001"}):
            with self.subTest(opts=opts), self.assertRaises(GuardError):
                self.arm(**opts)
    def test_bad_key_and_endpoint_rejected(self):
        with self.assertRaises(GuardError):
            CloreAPI(" bad token ")
        api=CloreAPI("a"*32)
        with self.assertRaisesRegex(GuardError,"unsupported_endpoint"):
            api._request("create_order",{"server_id":42})
    def test_transport_checks_response_and_keeps_token_private(self):
        class Response:
            def __init__(self, blob):self.blob=blob
            def __enter__(self):return self
            def __exit__(self, *args):pass
            def read(self, limit):return self.blob
        seen=[]
        def transport(req,timeout):
            seen.append((req.full_url,req.get_method(),req.get_header("Auth"),req.data))
            return Response(b'{"code":0,"orders":[]}')
        api=CloreAPI("SECRET_NOT_FOR_LOGS",transport=transport)
        self.assertEqual(api.orders(),[])
        self.assertEqual(seen[0][0],"https://api.clore.ai/v1/my_orders?return_completed=true")
        self.assertEqual(seen[0][2],"SECRET_NOT_FOR_LOGS")
        self.assertEqual(seen[0][1],"GET")
    def test_credential_must_use_systemd_file(self):
        with patch.dict("os.environ",{},clear=True):
            with self.assertRaisesRegex(GuardError,"systemd_credential_required"):
                credential()

if __name__ == "__main__":
    unittest.main()
