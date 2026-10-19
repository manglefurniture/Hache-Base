import importlib.util
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('access_gateway', Path(__file__).with_name('access_gateway.py'))
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def vast():
    return dict(provider='vast', instance_id='56667162', machine_id=151300, host_id=467312,
                gpu_count=8, host='ssh.example.org',
                port=22001, user='root', identity_file='/tmp/key',
                known_hosts='/tmp/known_hosts')


def salad():
    return dict(provider='salad', instance_id='8d47a11', machine_id=12, host_id=25,
                gpu_count=1, host='salad.example.org',
                port=22022, user='root', identity_file='/tmp/key',
                known_hosts='/tmp/known_hosts', organization='hache',
                project='prl-tests', group='prl-low')


class GatewayTests(unittest.TestCase):
    @staticmethod
    def live_vast(**changes):
        data = dict(id=56667162, actual_status='running',
                    machine_id=151300, host_id=467312, num_gpus=8,
                    ssh_host='ssh.example.org', ssh_port=22001)
        data.update(changes)
        return data

    def test_endpoint_is_pinned_to_provider_live_hardware(self):
        cases = [
            {'machine_id': 991},
            {'host_id': 998},
            {'num_gpus': 7},
            {'ssh_host': 'new.vast.ai'},
            {'ssh_port': 22002},
            {'ssh_port': None},
        ]
        for changed in cases:
            with self.subTest(changed=changed), self.assertRaisesRegex(
                    gate.AccessError, 'vast_endpoint_or_hardware_changed'):
                gate.require_running(vast(), send=lambda _: self.live_vast(**changed))

    def test_old_broker_without_ssh_fields_fails_closed(self):
        with self.assertRaisesRegex(gate.AccessError, 'vast_endpoint_or_hardware_changed'):
            gate.require_running(vast(), send=lambda _: dict(
                id=56667162, actual_status='running', machine_id=151300,
                host_id=467312, num_gpus=8))

    def test_gpu_probe_requires_expected_physical_count(self):
        with patch.object(gate,'ssh_args',return_value=['ssh','-T','fixed']):
            def runner(argv, **kwargs):
                return types.SimpleNamespace(returncode=0, stdout='0, RTX 5090, 58, 450, 100\\n', stderr='')
            with self.assertRaisesRegex(gate.AccessError,'ssh_gpu_count_mismatch'):
                gate.remote_probe(vast(),'gpu',send=lambda _:self.live_vast(),runner=runner)

    def test_fixed_read_only_actions(self):
        self.assertEqual(gate.operation('vast.status', {'instance_id':'56667162'})['action'], 'vast.status')
        for action, fields in [
            ('vast.stop', {}), ('salad.reallocate', {}), ('vast.status', {}),
            ('vast.list', {'instance_id':'1'}), ('vast.status', {'instance_id':'../1'}),
            ('salad.groups', {'organization':'x/y', 'project':'p'})]:
            with self.subTest(action=action, fields=fields), self.assertRaises(gate.AccessError):
                gate.operation(action, fields)

    def test_profile_rejects_untrusted_or_extra_fields(self):
        for bad in [
            dict(vast(), host='-ProxyCommand=bad'),
            dict(vast(), user='deploy-hache'),
            dict(vast(), port=True),
            dict(vast(), host_id=True),
            dict(vast(), gpu_count=0),
            dict(vast(), identity_file='/tmp/a', extra='x'),
            dict(vast(), instance_id='not-a-number'),
            dict(salad(), organization='../other')]:
            with self.subTest(bad=bad), self.assertRaises(gate.AccessError):
                gate.verify_profile(bad)

    def test_known_hosts_and_identity_are_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            key=root/'key'
            hosts=root/'known_hosts'
            key.write_text('fixture-not-a-real-key')
            hosts.write_text('fixture-not-a-real-host')
            key.chmod(0o600)
            hosts.chmod(0o644)
            data=dict(vast(), identity_file=str(key), known_hosts=str(hosts))
            argv=gate.ssh_args(data, 'gpu')
            self.assertIn('StrictHostKeyChecking=yes', argv)
            self.assertIn('IdentitiesOnly=yes', argv)
            self.assertEqual(argv[-1], gate.PROBES['gpu'])
            self.assertEqual(argv[-2], 'root@ssh.example.org')
            key.chmod(0o644)
            with self.assertRaises(gate.AccessError):
                gate.ssh_args(data, 'gpu')
            key.chmod(0o600)
            with self.assertRaises(gate.AccessError):
                gate.ssh_args(data, 'exec')

    def test_down_or_unready_instance_never_reaches_ssh(self):
        with patch.object(gate,'ssh_args',side_effect=AssertionError('SSH should not execute')):
            with self.assertRaisesRegex(gate.AccessError, 'vast_not_running'):
                gate.remote_probe(vast(), 'miner', send=lambda _: dict(id=56667162, actual_status='exited'))
            with self.assertRaisesRegex(gate.AccessError, 'salad_ssh_endpoint_unverified'):
                gate.remote_probe(salad(), 'gpu',
                                  send=lambda _: dict(instance_id='8d47a11', state='running',
                                                      ready=False, started=True))

    def test_ssh_probe_uses_no_shell_interpolation(self):
        with patch.object(gate,'ssh_args',return_value=['ssh','-T','fixed']):
            calls=[]
            def runner(argv, **kwargs):
                calls.append((argv, kwargs))
                return types.SimpleNamespace(returncode=0,stdout='2\n',stderr='')
            value=gate.remote_probe(vast(),'miner',
                        send=lambda _:self.live_vast(),runner=runner)
            self.assertEqual(value['output'], '2')
            self.assertEqual(calls[0][0],['ssh','-T','fixed'])
            self.assertNotIn('shell',calls[0][1])

    def test_private_profile_is_mandatory(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'profiles.json'
            p.write_text(json.dumps({'profiles': {'vast-56667162': vast()}}))
            p.chmod(0o644)
            with self.assertRaises(gate.AccessError):
                gate.profile_from_file(str(p),'vast-56667162')
            p.chmod(0o600)
            self.assertEqual(gate.profile_from_file(str(p),'vast-56667162')['provider'],'vast')
            with self.assertRaisesRegex(gate.AccessError,'profile_not_registered'):
                gate.profile_from_file(str(p),'missing')

    def test_error_does_not_emit_command_stderr(self):
        with patch.object(gate,'ssh_args',return_value=['ssh','-T','fixed']):
            def failed(*a,**kw): return types.SimpleNamespace(returncode=255,stdout='',stderr='SECRET')
            with self.assertRaisesRegex(gate.AccessError,'ssh_probe_failed') as caught:
                gate.remote_probe(vast(), 'gpu',
                  send=lambda _:self.live_vast(),runner=failed)
            self.assertNotIn('SECRET',str(caught.exception))


    def test_offline_registration_pins_live_metadata_without_starting(self):
        with tempfile.TemporaryDirectory() as folder:
            key = Path(folder)/'key'
            key.write_text('private-fixture-not-a-valid-key')
            key.chmod(0o600)
            path = Path(folder)/'hminer-access'/'profiles.json'
            events = []
            def api(request, **kwargs):
                events.append(request)
                return self.live_vast(actual_status='exited')
            answer = gate.register_vast('56667162', profiles_path=str(path),
                                        identity=str(key),
                                        known_hosts=str(Path(folder)/'absent-known-hosts'),
                                        send=api)
            self.assertTrue(answer['registered'])
            self.assertEqual(answer['ssh_trust'], 'unverified_must_pin_verified_host_key')
            self.assertEqual(events, [{'method':'query', 'operation':
                                       {'action':'vast.status','instance_id':'56667162'}}])
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            profile = json.loads(path.read_text())['profiles']['vast-56667162']
            self.assertEqual(profile['machine_id'],151300)
            self.assertEqual(profile['host_id'],467312)
            self.assertEqual(profile['gpu_count'],8)
            self.assertEqual(profile['host'],'ssh.example.org')
            with self.assertRaisesRegex(gate.AccessError, 'profiles_exist_no_overwrite'):
                gate.register_vast('56667162', profiles_path=str(path),
                                   identity=str(key), send=api)

    def test_register_needs_verified_provider_endpoint(self):
        with tempfile.TemporaryDirectory() as folder:
            key=Path(folder)/'key'
            key.write_text('fixture')
            key.chmod(0o600)
            filename=str(Path(folder)/'profiles.json')
            with self.assertRaises(gate.AccessError):
                gate.register_vast('56667162', profiles_path=filename,
                                   identity=str(key),
                                   send=lambda *a,**k:self.live_vast(ssh_host=None))
            self.assertFalse(Path(filename).exists())


if __name__ == '__main__':
    unittest.main()
