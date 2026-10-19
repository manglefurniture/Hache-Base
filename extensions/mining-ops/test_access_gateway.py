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
    return dict(provider='vast', instance_id='56667162', host='ssh.example.org',
                port=22001, user='root', identity_file='/tmp/key',
                known_hosts='/tmp/known_hosts')


def salad():
    return dict(provider='salad', instance_id='8d47a11', host='salad.example.org',
                port=22022, user='root', identity_file='/tmp/key',
                known_hosts='/tmp/known_hosts', organization='hache',
                project='prl-tests', group='prl-low')


class GatewayTests(unittest.TestCase):
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
            with self.assertRaisesRegex(gate.AccessError, 'salad_not_ready'):
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
                        send=lambda _:dict(id=56667162,actual_status='running'),runner=runner)
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
                  send=lambda _:dict(id=56667162,actual_status='running'),runner=failed)
            self.assertNotIn('SECRET',str(caught.exception))


if __name__ == '__main__':
    unittest.main()
