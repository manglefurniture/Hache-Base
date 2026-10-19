import json
import os
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch
import vast_provision_helper as v


def target():
    return {'instance_id':'56667162','machine_id':151300,'host_id':467312,
            'gpu_count':8,'ssh_host':'ssh8.vast.ai','ssh_port':10566,
            'key_file':'/etc/hache-mining-operator/ssh/vast56667162.key',
            'known_hosts':'/etc/hache-mining-operator/ssh/vast56667162.known_hosts',
            'release_commit':'a'*40,'archive_sha256':'b'*64}


def operation(step='stage'):
    return {'action':'vast.provision','instance_id':'56667162',
            'release_commit':'a'*40,'step':step}


def provider(**overrides):
    value=dict(id=56667162,machine_id=151300,host_id=467312,num_gpus=8,
               ssh_host='ssh8.vast.ai',ssh_port=10566,
               actual_status='running',intended_status='running')
    value.update(overrides)
    return value


class BrokerProvisionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)
        self.db=self.path/'test.sqlite'
        conn=sqlite3.connect(self.db)
        conn.execute('CREATE TABLE vast_leases (instance_id TEXT, phase TEXT, deadline INTEGER)')
        conn.execute('CREATE TABLE lease_guard_heartbeat (id INTEGER, completed_at INTEGER)')
        now=int(time.time())
        conn.execute("INSERT INTO vast_leases VALUES('56667162','armed',?)",(now+600,))
        conn.execute('INSERT INTO lease_guard_heartbeat VALUES(1,?)',(now,))
        conn.commit();conn.close()

    def tearDown(self):
        self.tmp.cleanup()

    def test_matching_running_instance_and_financial_lease(self):
        r=v.live_identity(operation(),target(),provider=lambda _:provider(),
                          database=self.db)
        self.assertEqual(r['gpu_count'],8)
        self.assertEqual(r['step'],'stage')
        self.assertEqual(r['ssh_port'],10566)
        self.assertNotIn('wallet',r)
        self.assertNotIn('key_file',r)
        with self.assertRaisesRegex(v.Reject,'operation_not_allowed'):
            v.live_identity(dict(operation(),step='reboot'),target(),
                            provider=lambda _:provider(),database=self.db)

    def test_fails_closed_for_identity_mismatch_or_stopped_gpu(self):
        for values in [dict(machine_id=1234),dict(host_id=13),dict(num_gpus=4),
                       dict(ssh_host='evil.example'),dict(ssh_port=10567),
                       dict(actual_status='exited'),dict(intended_status='stopped'),
                       dict(id=444)]:
            with self.subTest(values=values),self.assertRaisesRegex(
                v.Reject,'provider_identity_or_state_changed'):
                v.live_identity(operation(),target(),provider=lambda _,a=values:provider(**a),
                                database=self.db)

    def test_no_active_lease_no_provision_action(self):
        conn=sqlite3.connect(self.db)
        conn.execute("UPDATE vast_leases SET phase='closed'")
        conn.commit();conn.close()
        with self.assertRaisesRegex(v.Reject,'financial_lease_required'):
            v.live_identity(operation(),target(),provider=lambda _:provider(),
                            database=self.db)

    def test_expired_or_stale_guard_is_not_a_safe_lease(self):
        conn=sqlite3.connect(self.db)
        conn.execute('UPDATE lease_guard_heartbeat SET completed_at=1')
        conn.commit();conn.close()
        with self.assertRaisesRegex(v.Reject,'financial_lease_required'):
            v.live_identity(operation(),target(),provider=lambda _:provider(),
                            database=self.db)
        conn=sqlite3.connect(self.db)
        conn.execute('UPDATE lease_guard_heartbeat SET completed_at=?',(int(time.time()),))
        conn.execute('UPDATE vast_leases SET deadline=?',(int(time.time())+210,))
        conn.commit();conn.close()
        with self.assertRaisesRegex(v.Reject,'financial_lease_required'):
            v.live_identity(operation('apply'),target(),provider=lambda _:provider(),
                            database=self.db)

    def test_ssh_command_is_allowlisted_and_pinned(self):
        cmd=v.ssh_args(target(),operation('configure'))
        self.assertEqual(cmd[0],'/usr/bin/ssh')
        self.assertIn('StrictHostKeyChecking=yes',cmd)
        self.assertIn('ClearAllForwardings=yes',cmd)
        self.assertIn('BatchMode=yes',cmd)
        self.assertEqual(cmd[-1],'configure 56667162 '+'a'*40)
        self.assertNotIn('wallet', ' '.join(cmd))
        self.assertNotIn('ingest_key',' '.join(cmd))
        self.assertNotIn('curl',' '.join(cmd))

    def test_stage_archive_hash_and_secret_never_printed(self):
        payload=b'staged verified bytes'
        archive=self.path/('a'*40+'.tar.gz')
        archive.write_bytes(payload);archive.chmod(0o600)
        cfg=dict(target(),archive_sha256=__import__('hashlib').sha256(payload).hexdigest())
        private=self.path/'56667162.private.json'
        secret=b'PrivateSecretExample0123456789'
        envelope={'recipe':{'instance_id':'56667162','machine_id':'151300',
                            'host_id':'467312','gpu_count':8},'ingest_key':secret.decode()}
        private.write_text(json.dumps(envelope));private.chmod(0o600)
        def read_file(path,uid=0,**kwargs):
            return v.owner_file(path,uid=os.getuid(),**kwargs)
        with patch.object(v,'owner_file',side_effect=read_file):
            self.assertEqual(v.verified_payload(operation(),cfg,bundles=self.path),payload)
            self.assertEqual(v.verified_payload(operation('configure'),cfg,secrets_dir=self.path),
                             private.read_bytes())
        archive.write_bytes(b'changed')
        with patch.object(v,'owner_file',side_effect=read_file):
            with self.assertRaisesRegex(v.Reject,'archive_not_pinned'):
                v.verified_payload(operation(),cfg,bundles=self.path)

    def test_execute_never_starts_mining_or_runs_without_lease(self):
        import types
        calls=[]
        with patch.object(v,'verified_payload',return_value=b'secret-no-log'):
            def runner(argv,**kwargs):
                calls.append((argv,kwargs))
                return types.SimpleNamespace(returncode=0,stdout=json.dumps({
                    'ok':True,'status':'configured','mining_started':False}).encode())
            result=v.execute(operation('configure'),target(),
                    provider=lambda _:provider(),runner=runner,database=self.db)
        self.assertFalse(result['mining_started'])
        self.assertEqual(calls[0][1]['input'],b'secret-no-log')
        self.assertNotIn('secret-no-log',' '.join(calls[0][0]))
        conn=sqlite3.connect(self.db)
        conn.execute("UPDATE vast_leases SET phase='closed'");conn.commit();conn.close()
        with self.assertRaisesRegex(v.Reject,'financial_lease_required'):
            v.execute(operation('configure'),target(),provider=lambda _:provider(),
                      runner=lambda *a,**kw:self.fail('SSH must not execute'),database=self.db)


if __name__=='__main__':
    unittest.main()
