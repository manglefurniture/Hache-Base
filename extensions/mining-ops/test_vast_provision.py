import hashlib
import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('vast_provision',ROOT/'vast_provision.py')
v=importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)


def profile():
    return {'provider':'vast','instance_id':'56667162','machine_id':151300,
            'host_id':467312,'gpu_count':8,'host':'ssh8.vast.ai','port':10566,
            'user':'root','identity_file':'/tmp/key','known_hosts':'/tmp/known_hosts'}


def active():
    return {'id':56667162,'machine_id':151300,'host_id':467312,
            'num_gpus':8,'ssh_host':'ssh8.vast.ai','ssh_port':10566,
            'actual_status':'running'}


class VastProvisionTests(unittest.TestCase):
    def test_offline_tar_bundle_allowlist(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'bundle.tar.gz'
            with tarfile.open(path,mode='w:gz') as tar:
                for name in sorted(v.FILES):
                    data=(name+'\n').encode()
                    info=tarfile.TarInfo(name)
                    info.size=len(data)
                    tar.addfile(info,io.BytesIO(data))
            path.chmod(0o600)
            digest=hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(v.validate_archive(path,digest),path.read_bytes())
            with self.assertRaisesRegex(v.DeployError,'sha256_mismatch'):
                v.validate_archive(path,'0'*64)
            evil=Path(tmp)/'evil.tar.gz'
            with tarfile.open(evil,mode='w:gz') as tar:
                info=tarfile.TarInfo('../../etc/passwd')
                info.size=1
                tar.addfile(info,io.BytesIO(b'x'))
            evil.chmod(0o600)
            with self.assertRaisesRegex(v.DeployError,'unexpected_bundle_contents'):
                v.validate_archive(evil,hashlib.sha256(evil.read_bytes()).hexdigest())

    def test_profile_does_not_allow_other_instance(self):
        with patch.object(v.gateway,'verify_profile'):
            with self.assertRaisesRegex(v.DeployError,'target_not_approved'):
                v.verify_target(profile(),'999',
                    send=lambda *_:self.fail('must not contact provider'))

    def test_api_rejects_stopped_and_swapped_hardware(self):
        with patch.object(v.gateway,'verify_profile'):
            with self.assertRaises(v.gateway.AccessError):
                v.verify_target(profile(),'56667162',
                    send=lambda *_:dict(active(),actual_status='exited'))
            with self.assertRaises(v.gateway.AccessError):
                v.verify_target(profile(),'56667162',
                    send=lambda *_:dict(active(),machine_id=9999))

    def test_only_fixed_ssh_commands_are_emitted(self):
        with patch.object(v.gateway,'ssh_args',return_value=['ssh','-T','root@host','date -u']):
            calls=[]
            def runner(command, **kwargs):
                calls.append((command,kwargs))
                return types.SimpleNamespace(returncode=0,stdout=b'ok',stderr=b'')
            out=v.run_remote(profile(),'stage','a'*40,bundle=b'fake fixture',runner=runner)
            self.assertEqual(out['accepted'],True)
            self.assertEqual(out['mining_started'],False)
            self.assertEqual(calls[0][0][0],'ssh')
            self.assertNotIn('start',calls[0][0][-1])
            self.assertNotIn('rm -rf',calls[0][0][-1])
            self.assertEqual(calls[0][1]['input'],b'fake fixture')
            calls.clear()
            out=v.run_remote(profile(),'apply','b'*40,runner=runner)
            self.assertEqual(out['action'],'apply')
            self.assertIn('--confirm-instance 56667162',calls[0][0][-1])
            self.assertNotIn('--start',calls[0][0][-1])
            self.assertIsNone(calls[0][1]['input'])

    def test_never_print_ssh_errors(self):
        with patch.object(v.gateway,'ssh_args',return_value=['ssh','host','date']):
            def fail(*args,**kwargs):
                return types.SimpleNamespace(returncode=255,stdout=b'',stderr=b'PRIVATE KEY MATERIAL')
            with self.assertRaisesRegex(v.DeployError,'ssh_stage_failed') as caught:
                v.run_remote(profile(),'stage','a'*40,bundle=b'data',runner=fail)
            self.assertNotIn('PRIVATE',str(caught.exception))


if __name__=='__main__':
    unittest.main()
