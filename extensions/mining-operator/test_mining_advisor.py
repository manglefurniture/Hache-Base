import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

SPEC = importlib.util.spec_from_file_location('mining_advisor', Path(__file__).with_name('mining_advisor.py'))
advisor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(advisor)

NOW = datetime.now(timezone.utc).replace(microsecond=0)


def observation(i, *, gpu='RTX 5090', variant='desktop', mined=12.0, shares=100, provider='vast', at=None):
    return {'evidence_id': f'prl-observation-{i:03}', 'provider': provider, 'gpu_name': gpu,
            'variant': variant, 'gpu_count': 1, 'billed_hours': 2.0, 'prl_mined': mined,
            'setup_minutes': 10, 'accepted_shares': shares,
            'observed_at': (at or NOW-timedelta(hours=i)).isoformat()}


def offer(*, gpu='RTX 5090', variant='desktop', price=0.45, reliability=0.97):
    return {'ok':True,'result':{'offers':[{'id':123, 'machine_id':33,'host_id':22,
            'gpu_name': gpu,'variant':variant,'num_gpus':1,'dph_total':price,
            'reliability2':reliability}]}}


def market(price=1.9):
    return {'price_usd_per_prl':price, 'price_observed_at':(NOW-timedelta(minutes=5)).isoformat(),
            'pool_fee_fraction':0.02,'exchange_fee_fraction':0.01,'duration_hours':4,
            'cost_buffer_fraction':0.15,'extra_charges_usd':0.2,'min_net_usd':0.10}


class MiningAdvisorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.dbfile=os.path.join(self.temp.name,'history.db')
        self.mem=advisor.Memory(self.dbfile)

    def tearDown(self):
        self.mem.close()
        self.temp.cleanup()

    def seed(self):
        for i in range(1,4):
            self.mem.record(observation(i))

    def test_no_measurements_never_recommends(self):
        result=advisor.evaluate(offer(),self.mem,market=market(),now=NOW)
        self.assertEqual(result['offers'][0]['status'],'needs_verification')
        self.assertIn('insufficient_recent_prl_measurements',result['offers'][0]['reasons'])
        self.assertFalse(result['renting_enabled'])

    def test_conservative_projection_and_cost_buffer(self):
        self.seed()
        result=advisor.evaluate(offer(),self.mem,market=market(),now=NOW)['offers'][0]
        self.assertEqual(result['status'],'candidate_for_manual_quote')
        self.assertEqual(result['measured_samples'],3)
        self.assertAlmostEqual(result['conservative_prl'],23)
        self.assertGreater(result['projected_net_usd'],0)
        self.assertGreater(result['projected_cost_usd'],4*0.45)
        self.assertIn('requires_fresh_all_in_quote_and_authorization',result['reasons'])

    def test_negative_net_rejected(self):
        self.seed()
        result=advisor.evaluate(offer(price=25),self.mem,market=market(price=0.1),now=NOW)['offers'][0]
        self.assertEqual(result['status'],'reject')
        self.assertIn('net_below_threshold',result['reasons'])

    def test_laptop_and_desktop_cannot_share_yield(self):
        self.seed()
        result=advisor.evaluate(offer(gpu='RTX 5090 Laptop',variant='laptop'),self.mem,market=market(),now=NOW)['offers'][0]
        self.assertEqual(result['status'],'needs_verification')
        self.assertIn('insufficient_recent_prl_measurements',result['reasons'])

    def test_missing_variant_not_assumed_desktop(self):
        self.seed()
        result=advisor.evaluate(offer(variant=None),self.mem,market=market(),now=NOW)['offers'][0]
        self.assertIn('gpu_variant_unverified',result['reasons'])

    def test_stale_measurements_ignored(self):
        for i in range(1,4):
            self.mem.record(observation(i,at=NOW-timedelta(days=20,hours=i)))
        result=advisor.evaluate(offer(),self.mem,market=market(),now=NOW)['offers'][0]
        self.assertIn('insufficient_recent_prl_measurements',result['reasons'])

    def test_low_reliability_rejected(self):
        self.seed()
        result=advisor.evaluate(offer(reliability=0.75),self.mem,market=market(),now=NOW)['offers'][0]
        self.assertEqual(result['status'],'reject')

    def test_bad_or_stale_price_fails_closed(self):
        self.seed()
        m=market()
        m['price_observed_at']=(NOW-timedelta(hours=3)).isoformat()
        with self.assertRaisesRegex(ValueError,'stale_market_price'):
            advisor.evaluate(offer(),self.mem,market=m,now=NOW)
        m=market()
        m['price_usd_per_prl']=float('nan')
        with self.assertRaisesRegex(ValueError,'invalid_price'):
            advisor.evaluate(offer(),self.mem,market=m,now=NOW)

    def test_observations_immutable_by_evidence_id(self):
        record=observation(1)
        self.mem.record(record)
        self.mem.record(record)
        with self.assertRaisesRegex(ValueError,'evidence_id_conflict'):
            self.mem.record(dict(record,prl_mined=99.0))
        self.assertEqual(self.mem.db.execute('SELECT COUNT(*) FROM prl_observations').fetchone()[0],1)

    def test_no_shares_does_not_become_evidence(self):
        for i in range(1,4):self.mem.record(observation(i,shares=0))
        self.assertIsNone(self.mem.summary('vast','RTX5090:desktop',NOW))

    def test_clore_without_gpu_count_is_not_ranked(self):
        self.seed()
        r=advisor.evaluate({'prl_gpu':[{'id':42,'gpu':'RTX 5090','on_demand_usd_hour':0.1}]},self.mem,market=market(),now=NOW)
        self.assertEqual(r['offers'][0]['status'],'needs_verification')
        self.assertIn('gpu_count_and_quote_not_verified',r['offers'][0]['reasons'])

    def test_no_provider_success_no_eval(self):
        with self.assertRaisesRegex(ValueError,'provider_query_failed'):
            advisor.evaluate({'ok':False,'error':'timeout'},self.mem,market=market(),now=NOW)

    def test_malformed_results_and_duplicates(self):
        self.seed()
        raw=offer()['result']
        raw['offers'] += [raw['offers'][0].copy()]
        r=advisor.evaluate(raw,self.mem,market=market(),now=NOW)
        self.assertEqual(r['offers'][0]['status'],'candidate_for_manual_quote')
        self.assertIn('invalid_or_duplicate_offer_id',r['offers'][1]['reasons'])

    def test_zero_share_hours_cannot_satisfy_duration_gate(self):
        for i in range(1,4):
            self.mem.record(dict(observation(i),billed_hours=0.25))
        self.mem.record(dict(observation(4),billed_hours=2.25,accepted_shares=0))
        result=advisor.evaluate(offer(),self.mem,market=market(),now=NOW)['offers'][0]
        self.assertEqual(result['status'],'needs_verification')
        self.assertIn('insufficient_recent_prl_measurements',result['reasons'])

    def test_cli_persists_across_runs_without_provider_mutation(self):
        folder=Path(self.temp.name)
        records=folder/'observations.json'
        records.write_text(json.dumps([observation(i) for i in range(1,4)]))
        run=subprocess.run([sys.executable,str(Path(__file__).with_name('mining_advisor.py')),'--database',str(folder/'cli.db'),'--import-measurements',str(records)],capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stderr)
        offers=folder/'offers.json';offers.write_text(json.dumps(offer()))
        prices=folder/'market.json';prices.write_text(json.dumps(market()))
        run=subprocess.run([sys.executable,str(Path(__file__).with_name('mining_advisor.py')),'--database',str(folder/'cli.db'),'--offers',str(offers),'--market',str(prices)],capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stderr)
        self.assertEqual(json.loads(run.stdout)['offers'][0]['status'],'candidate_for_manual_quote')

if __name__=='__main__':unittest.main()
