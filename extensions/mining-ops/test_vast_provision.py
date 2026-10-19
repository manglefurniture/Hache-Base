import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
from pathlib import Path
import stat
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


def approval(files=None,**changes):
    a={'repository':'manglefurniture/HACHE-MINER',
       'commit':'a'*40,'instance_id':'56667162','machine_id':151300,
       'host_id':467312,'gpu_count':8,'ssh_host':'ssh8.vast.ai',
       'ssh_port':10566,'not_before':1000,'expires_at':1400,
       'approved_action':'stage','archive_sha256':'0'*64,
       'files':files or {name:'b'*40 for name in v.FILES}}
    a.update(changes)
    return a


def build_tar(path, overrides=None):
    data={}
    with tarfile.open(path,mode='w:gz') as tar:
        for name in sorted(v.FILES):
            content=(overrides or {}).get(name,(name+'\n').encode())
            data[name]=content
            info=tarfile.TarInfo(name)
            info.size=len(content)
            tar.addfile(info,io.BytesIO(content))
    path.chmod(0o600)
    return data


class VastProvisionTests(unittest.TestCase):
    def test_git_blob_uses_actual_git_format(self):
        self.assertEqual(v.git_blob(b'hello world\n'),
                         '3b18e512dba79e4c8300dd08aeb37f8e728b8dad')

    def test_tar_requires_pinned_github_blob_for_every_member(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'bundle.tar.gz'
            data=build_tar(path)
            a=approval(files={name:v.git_blob(contents) for name,contents in data.items()},
                       archive_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            with patch.object(v.gateway,'safe_file',side_effect=lambda x,private: str(x)):
                self.assertEqual(v.validate_archive(path,a),path.read_bytes())
                with self.assertRaisesRegex(v.DeployError,'sha256_mismatch'):
                    v.validate_archive(path,dict(a,archive_sha256='0'*64))

                # A fraudulent operator may correctly hash a malicious tar.
                # The pinned GitHub blob IDs still reject even a one-byte change.
                modified=Path(tmp)/'modified.tar.gz'
                build_tar(modified,{'vast-onstart.sh':b'malicious code\n'})
                altered=dict(a,archive_sha256=hashlib.sha256(modified.read_bytes()).hexdigest())
                with self.assertRaisesRegex(v.DeployError,'unapproved_github_blob'):
                    v.validate_archive(modified,altered)

                evil=Path(tmp)/'evil.tar.gz'
                with tarfile.open(evil,mode='w:gz') as tar:
                    info=tarfile.TarInfo('../../etc/passwd')
                    info.size=1
                    tar.addfile(info,io.BytesIO(b'x'))
                evil.chmod(0o600)
                with self.assertRaisesRegex(v.DeployError,'unexpected_bundle_contents'):
                    v.validate_archive(evil,dict(a,archive_sha256=hashlib.sha256(evil.read_bytes()).hexdigest()))

    def test_explicit_approval_separates_stage_from_apply(self):
        a=approval()
        v.check_approval(a,profile(),'stage','a'*40,now=1100)
        with self.assertRaisesRegex(v.DeployError,'action_or_commit_not_approved'):
            v.check_approval(a,profile(),'apply','a'*40,now=1100)
        with self.assertRaisesRegex(v.DeployError,'action_or_commit_not_approved'):
            v.check_approval(a,profile(),'stage','b'*40,now=1100)
        with self.assertRaisesRegex(v.DeployError,'root_approval_expired'):
            v.check_approval(a,profile(),'stage','a'*40,now=1401)
        for other in [dict(profile(),instance_id='1234'),
                      dict(profile(),machine_id=999),
                      dict(profile(),host='ssh9.vast.ai')]:
            with self.assertRaisesRegex(v.DeployError,'profile_not_approved'):
                v.check_approval(a,other,'stage','a'*40,now=1100)

    def test_root_approval_file_permissions_and_expiry(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'approval.json'
            doc=approval()
            path.write_text(json.dumps(doc))
            path.chmod(0o600)
            old=path.lstat()
            with patch.object(v.Path,'lstat',return_value=types.SimpleNamespace(
                    st_mode=stat.S_IFREG | 0o600,st_uid=0,st_nlink=1)):
                self.assertEqual(v.load_approval(path,now=1100)['commit'],'a'*40)
                with self.assertRaisesRegex(v.DeployError,'invalid_or_expired_root_approval'):
                    v.load_approval(path,now=1401)
            with patch.object(v.Path,'lstat',return_value=types.SimpleNamespace(
                    st_mode=stat.S_IFREG | 0o644,st_uid=0,st_nlink=1)):
                self.assertEqual(v.load_approval(path,now=1100)['approved_action'],'stage')
            with patch.object(v.Path,'lstat',return_value=types.SimpleNamespace(
                    st_mode=stat.S_IFREG | 0o666,st_uid=0,st_nlink=1)):
                with self.assertRaisesRegex(v.DeployError,'unsafe_root_approval'):
                    v.load_approval(path,now=1100)
            with patch.object(v.Path,'lstat',return_value=types.SimpleNamespace(
                    st_mode=stat.S_IFREG | 0o600,st_uid=1001,st_nlink=1)):
                with self.assertRaisesRegex(v.DeployError,'unsafe_root_approval'):
                    v.load_approval(path,now=1100)


    def test_direct_untrusted_ssh_execution_is_rejected(self):
        with patch.object(v.pwd,'getpwnam',return_value=types.SimpleNamespace(pw_uid=os.geteuid()+1)):
            with self.assertRaisesRegex(v.DeployError,'trusted_executor_required'):
                v.run_remote(profile(),'stage','a'*40,approval=approval(),
                             bundle=b'fake',runner=lambda *a,**kw:self.fail('SSH called'))

    def test_one_use_claim_survives_failure_and_excludes_untrusted_user(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)/'claims'
            directory.mkdir(mode=0o700)
            a=approval()
            claim=v.claim_approval(a,directory=directory,executor_uid=os.geteuid())
            self.assertEqual(len(claim),64)
            with self.assertRaisesRegex(v.DeployError,'approval_already_consumed'):
                v.claim_approval(a,directory=directory,executor_uid=os.geteuid())
            with self.assertRaisesRegex(v.DeployError,'trusted_executor_required'):
                v.claim_approval(dict(a,commit='b'*40),directory=directory,
                                 executor_uid=os.geteuid()+1)
            directory.chmod(0o777)
            with self.assertRaisesRegex(v.DeployError,'unsafe_claim_store'):
                v.claim_approval(dict(a,commit='c'*40),directory=directory,
                                 executor_uid=os.geteuid())

    def test_remote_stage_atomic_idempotent_and_recoverable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            archive=root/'bundle.tar.gz'
            contents=build_tar(archive)
            digest=hashlib.sha256(archive.read_bytes()).hexdigest()
            expected={name:v.git_blob(data) for name,data in contents.items()}
            dest=root/'releases'/('a'*40)
            conf=root/'etc-hache-vast'
            binding=dict(instance_id='56667162',machine_id='151300',
                         host_id='467312',gpu_count=8,
                         ssh_host='ssh8.vast.ai',ssh_port=10566)
            argv=[sys.executable,'-c',v.REMOTE_STAGE_PY,str(dest),
                  json.dumps(expected),digest,json.dumps(binding),str(conf)]
            good=subprocess.run(argv,input=archive.read_bytes(),capture_output=True)
            self.assertEqual(good.returncode,0,good.stderr.decode()[:500])
            self.assertEqual(json.loads((conf/'host-binding.json').read_text()),binding)
            self.assertEqual({p.name:p.read_bytes() for p in dest.iterdir()},contents)
            again=subprocess.run(argv,input=archive.read_bytes(),capture_output=True)
            self.assertEqual(again.returncode,0,again.stderr.decode()[:500])
            self.assertEqual(list((root/'releases').glob('.stage-*')),[])
            other=list(argv)
            other[3]=str(root/'releases'/('b'*40))
            truncated=subprocess.run(other,input=archive.read_bytes()[:20],capture_output=True)
            self.assertNotEqual(truncated.returncode,0)
            self.assertFalse(Path(other[3]).exists())
            self.assertEqual(list((root/'releases').glob('.stage-*')),[])
            retry=subprocess.run(other,input=archive.read_bytes(),capture_output=True)
            self.assertEqual(retry.returncode,0,retry.stderr.decode()[:500])
            (Path(other[3])/'vast-onstart.sh').write_text('tamper')
            conflict=subprocess.run(other,input=archive.read_bytes(),capture_output=True)
            self.assertNotEqual(conflict.returncode,0)

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

    def test_remote_stage_and_apply_both_verify_git_blobs(self):
        a=approval()
        stage=v.remote_integrity_command(a,'/root/hache-vast/releases/'+'a'*40)
        self.assertIn('python3 -c ',stage)
        self.assertIn('actual==expected',stage)
        with patch.object(v,'require_executor'):
            with self.assertRaisesRegex(v.DeployError,'root_approval_required'):
                v.run_remote(profile(),'apply','a'*40,runner=lambda *a,**kw:
                             self.fail('unapproved SSH access'))
        self.assertNotIn('rm -rf',stage)

    def test_only_fixed_ssh_commands_are_emitted(self):
        with patch.object(v.gateway,'ssh_args',return_value=['ssh','-T','root@host','date -u']), \
             patch.object(v,'check_approval'), patch.object(v,'require_executor'):
            calls=[]
            def runner(command,**kwargs):
                calls.append((command,kwargs))
                return types.SimpleNamespace(returncode=0,stdout=b'ok',stderr=b'')
            out=v.run_remote(profile(),'stage','a'*40,bundle=b'fake fixture',approval=approval(),runner=runner)
            self.assertEqual(out['accepted'],True)
            self.assertFalse(out['mining_started'])
            self.assertNotIn('rm -rf',calls[0][0][-1])
            self.assertEqual(calls[0][1]['input'],b'fake fixture')
            calls.clear()
            out=v.run_remote(profile(),'apply','b'*40,approval=approval(approved_action='apply',commit='b'*40),runner=runner)
            self.assertEqual(out['action'],'apply')
            self.assertIn('--confirm-instance 56667162',calls[0][0][-1])
            self.assertNotIn('--start',calls[0][0][-1])

    def test_never_print_ssh_errors(self):
        with patch.object(v.gateway,'ssh_args',return_value=['ssh','host','date']), \
             patch.object(v,'check_approval'), patch.object(v,'require_executor'):
            def fail(*args,**kwargs):
                return types.SimpleNamespace(returncode=255,stdout=b'',stderr=b'PRIVATE KEY MATERIAL')
            with self.assertRaisesRegex(v.DeployError,'ssh_stage_failed') as caught:
                v.run_remote(profile(),'stage','a'*40,bundle=b'data',approval=approval(),runner=fail)
            self.assertNotIn('PRIVATE',str(caught.exception))


if __name__=='__main__':
    unittest.main()
