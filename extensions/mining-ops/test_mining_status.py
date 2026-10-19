import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('mining_status', Path(__file__).with_name('mining_status.py'))
ops = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ops)


class MiningDiagnosticsTests(unittest.TestCase):
    def test_stale_receive_does_not_mask_stale_origin(self):
        item = dict(instance_id=1, enabled=1, sample_age_s=200, receive_age_s=2)
        result = ops.evaluate({'vast': [item]}, {}, {})
        self.assertEqual(result, [{'code': 'vast_telemetry_stale_or_missing', 'target': '1'}])

    def test_registered_but_never_observed_is_unknown(self):
        result = ops.evaluate({'vast': [dict(instance_id=1, enabled=1)]}, {}, {})
        self.assertEqual(result[0]['code'], 'vast_telemetry_stale_or_missing')

    def test_gpu_zero_is_low_not_missing(self):
        item = dict(instance_id=1, enabled=1, sample_age_s=10, receive_age_s=10,
                    gpu_count=8, reported_gpus=8, total_ths=0, low_ths=2800)
        self.assertEqual(ops.evaluate({'vast': [item]}, {}, {})[0]['code'],
                         'vast_low_hashrate_snapshot')

    def test_disabled_instance_not_reported_as_missing(self):
        self.assertEqual(ops.evaluate({'vast': [dict(instance_id=1, enabled=0)]}, {}, {}), [])

    def test_partial_and_missing_project_are_visible(self):
        data = dict(sync=[dict(source='salad:test/default', age_s=20, status='partial')],
                    salad=[dict(organization='test', project='default', enabled=1, latest_age_s=None)])
        self.assertEqual(len(ops.evaluate(data, {}, {})), 2)

    def test_state_deduplicates_without_timestamp_noise(self):
        with tempfile.TemporaryDirectory() as folder:
            alerts = [{'code': 'sync_error', 'target': 'test'}]
            result = dict(alerts=alerts, fingerprint=ops.fingerprint(alerts), checked_at='first')
            ops.write_state(folder, result)
            self.assertTrue(result['changed'])
            result['checked_at'] = 'second'
            ops.write_state(folder, result)
            self.assertFalse(result['changed'])
            result['alerts'] = []
            result['fingerprint'] = ops.fingerprint([])
            ops.write_state(folder, result)
            self.assertTrue(json.loads((Path(folder)/'latest.json').read_text())['changed'])

    def test_queries_are_select_and_exclude_sensitive_tables(self):
        for query in ops.QUERIES.values():
            self.assertTrue(query.lstrip().startswith('SELECT '))
            for forbidden in ('secret_store', 'administrators', 'trusted_devices', 'wallets'):
                self.assertNotIn(forbidden, query)


if __name__ == '__main__':
    unittest.main()
