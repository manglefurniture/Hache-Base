"""Offline Clore worker liveness + financial cancellation integration tests."""
import io
import json
from http.client import IncompleteRead
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from clore_cancel_guard import arm, db_open, tick, GuardError
from clore_pool_watch import enroll, check, KryptexAPI, PoolError, SILENCE_SECONDS

WALLET = "prl1" + "q" * 55

class FakePool:
    def __init__(self, stamp=None, fail=False):
        self.stamp, self.fail, self.calls = stamp, fail, []
    def last_share(self, wallet, worker):
        self.calls.append((wallet, worker))
        if self.fail:
            raise PoolError("pool_unavailable")
        return self.stamp

class FakeClore:
    def __init__(self, valid_order=None, fail_get=False, fail_cancel=False):
        self.order = valid_order
        self.fail_get = fail_get
        self.fail_cancel = fail_cancel
        self.cancels = []
    def orders(self):
        if self.fail_get:
            raise GuardError("provider_request_failed")
        return [self.order] if self.order else []
    def cancel(self, order_id):
        self.cancels.append(order_id)
        if self.fail_cancel:
            raise GuardError("provider_request_failed")

class IndependentPoolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = db_open(Path(self.tmp.name)/"finance.sqlite")
        self.db.execute("INSERT INTO clore_cancel_heartbeat VALUES(1,1000)")
        self.provider_order = dict(id=777, si=121322, ct=1000, price="10",
                                   fee="0", spend="0", creation_fee="0",
                                   currency="USD-Blockchain", spot=True, expired=False)
        arm(self.db, order_id=777,server_id=121322,daily_bid_usd="10",
            budget_usd="2",creation_fee_usd="0",max_minutes=60,created_at=1000,
            provider_order=self.provider_order, now=1000,timer_check=lambda:True)
        self.lease = self.db.execute("SELECT * FROM clore_cancel_leases").fetchone()
    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()
    def enable(self):
        return enroll(self.db,order_id=777,wallet=WALLET,now=1001)
    def tick(self, pool, now, clore=None):
        clore = clore or FakeClore(self.provider_order)
        return clore,tick(self.db,clore,now=now,delay=lambda _:None,pool=pool)

    def test_legacy_leases_are_unmodified(self):
        provider,result=self.tick(FakePool(fail=True),now=1301)
        self.assertEqual(result["status"], "watching")
        self.assertEqual(provider.cancels, [])

    def test_never_produced_early_cancels_after_creation_grace(self):
        self.enable()
        p,r=self.tick(FakePool(),now=1299)
        self.assertEqual(r["status"],"watching")
        self.assertEqual(p.cancels,[])
        p,r=self.tick(FakePool(),now=1300)
        self.assertEqual(r["status"],"cancel_submitted_unverified")
        self.assertEqual(p.cancels,[777])
        self.assertEqual(self.db.execute("SELECT phase FROM clore_cancel_leases").fetchone()[0],"armed")
        p.order={**self.provider_order,"expired":True}
        result=tick(self.db,p,now=1330,delay=lambda _:None,pool=FakePool())
        self.assertEqual(result["status"],"verified_closed")

    def test_new_shares_allow_running_then_stale_cancel(self):
        self.enable()
        p,r=self.tick(FakePool(1290),now=1295)
        self.assertEqual(r["status"],"watching")
        p,r=self.tick(FakePool(1290),now=1589)
        self.assertEqual(r["status"],"watching")
        p,r=self.tick(FakePool(1290),now=1590)
        self.assertEqual(r["status"],"cancel_submitted_unverified")
        self.assertEqual(p.cancels,[777])

    def test_network_outage_cannot_refresh_cached_last_share(self):
        self.enable()
        self.tick(FakePool(1250),now=1250)
        p,r=self.tick(FakePool(fail=True),now=1549)
        self.assertEqual(r["status"],"watching")
        p,r=self.tick(FakePool(fail=True),now=1550)
        self.assertEqual(r["status"],"cancel_submitted_unverified")
        self.assertEqual(p.cancels,[777])

    def test_provider_get_timeout_still_attempts_cancel_if_pool_stale(self):
        self.enable()
        clore=FakeClore(fail_get=True)
        p,r=self.tick(FakePool(),now=1300,clore=clore)
        self.assertEqual(r["status"],"cancel_submitted_unverified")
        self.assertEqual(clore.cancels,[777])

    def test_repeated_cancel_retries_until_real_expiry(self):
        self.enable()
        clore=FakeClore(self.provider_order,fail_cancel=True)
        with self.assertRaisesRegex(GuardError,"cancel_failed_retry_next_tick"):
            self.tick(FakePool(),1300,clore)
        self.assertEqual(clore.cancels,[777])
        clore.fail_cancel=False
        self.tick(FakePool(),1330,clore)
        self.assertEqual(clore.cancels,[777,777])

    def test_identity_and_enrollment_validation(self):
        with self.assertRaisesRegex(PoolError,"invalid_pool_wallet"):
            enroll(self.db,order_id=777,wallet="https://attacker/",now=1001)
        with self.assertRaisesRegex(PoolError,"order_not_financially_armed"):
            enroll(self.db,order_id=778,wallet=WALLET,now=1001)
        with self.assertRaisesRegex(PoolError,"monitor_enrollment_too_late"):
            enroll(self.db,order_id=777,wallet=WALLET,now=1300)
        self.enable()
        with self.assertRaisesRegex(PoolError,"monitor_already_enrolled"):
            self.enable()
        self.db.execute("UPDATE clore_pool_monitors SET server_id=9 WHERE order_id=777")
        self.assertEqual(check(self.db,self.lease,now=1005,pool=FakePool(1004)),
                         "pool_monitor_identity_mismatch")

    def test_truncated_pool_read_does_not_prevent_financial_cutoff(self):
        self.enable()
        class TruncatedResponse:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *a): return None
            def read(self, n): raise IncompleteRead(b'{', 10)
        pool = KryptexAPI(transport=lambda *a, **kw: TruncatedResponse())
        provider, result = self.tick(pool, now=5000)
        self.assertEqual(result['status'], 'cancel_submitted_unverified')
        self.assertEqual(provider.cancels, [777])
        self.assertEqual(self.db.execute('SELECT phase FROM clore_cancel_leases').fetchone()[0], 'armed')

    def test_untrusted_pool_clock_never_extends_recovery(self):
        self.enable()
        p,r=self.tick(FakePool(999999),now=1300)
        self.assertEqual(r["status"],"cancel_submitted_unverified")
        self.assertEqual(p.cancels,[777])

class PoolAPIContractTests(unittest.TestCase):
    def fetch(self, data):
        class Response:
            status=200
            def __init__(self, body): self.body=body
            def __enter__(self):return self
            def __exit__(self,*args):return None
            def read(self,n):return self.body
        calls=[]
        def transport(request,timeout):
            calls.append((request.full_url,request.get_method(),timeout))
            return Response(json.dumps(data).encode())
        return KryptexAPI(transport=transport),calls

    def test_correct_worker_and_read_only_url(self):
        api,calls=self.fetch({"results":[
            {"worker":"CLORE-778","last_share":1201},
            {"worker":"CLORE-777","last_share":1234,"hashrate":0}
        ]})
        self.assertEqual(api.last_share(WALLET,"CLORE-777"),1234)
        self.assertEqual(calls,[(f"https://pool.kryptex.com/prl/api/v3/miner/workers/{WALLET}","GET",8)])

    def test_partial_duplicate_missing_and_invalid_responses(self):
        for payload in ({"results":[]},):
            api,_=self.fetch(payload)
            self.assertIsNone(api.last_share(WALLET,"CLORE-777"))
        for payload in ({"count":3,"results":[]}, {"results":[
                {"worker":"CLORE-777","last_share":12},
                {"worker":"CLORE-777","last_share":13}]},
                {"results":[{"worker":"CLORE-777","last_share":"1234"}]},
                {"results":"unknown"}):
            with self.subTest(payload=payload):
                api,_=self.fetch(payload)
                with self.assertRaises(PoolError):
                    api.last_share(WALLET,"CLORE-777")

if __name__ == "__main__":
    unittest.main()
