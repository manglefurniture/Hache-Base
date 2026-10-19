#!/usr/bin/env python3
"""Deployment gate regression suite; temporary directories only, no systemctl or provider calls."""
import hashlib
import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import deploy_gate as d


def fixture_archive(filename, target):
    content = {}
    items = d.TARGETS[target]['anchors'] + ['README.md']
    with tarfile.open(filename, 'w:gz') as tar:
        for name in items:
            data = (name+' fixture\n').encode()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info,io.BytesIO(data))
            content[name]=data
    return content


class GateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.rr=self.root/'miner';self.rr.mkdir()
        self.bb=self.root/'base';self.bb.mkdir()
        for target,root in (('hache-miner',self.rr),('hache-base',self.bb)):
            releases=root/'releases';releases.mkdir()
            commit='a'*40
            release=releases/commit
            (release/'extensions/mining-operator').mkdir(parents=True)
            suffix = '/extensions/mining-operator' if target=='hache-base' else ''
            (root/'current').symlink_to(str(release)+suffix)
        self.inbox=self.root/'inbox'
        self.state=self.root/'state'
        self.grants=self.root/'grants'
        for x in (self.inbox,self.state,self.grants): x.mkdir(mode=0o700)
        self.cfg={'database':str(self.state/'db.sqlite'),
                  'state_dir':str(self.state),'inbox':str(self.inbox),
                  'grants':str(self.grants),'agent_uid':os.getuid()}
        self.fix=patch.dict(d.TARGETS, {
            'hache-miner':dict(d.TARGETS['hache-miner'],root=str(self.rr)),
            'hache-base':dict(d.TARGETS['hache-base'],root=str(self.bb))})
        self.fix.start()
        self.calls=[]
        self.gate=d.Gate(self.cfg,owner_uid=os.getuid(),
                         now=lambda:1000,
                         deploy_fn=lambda op,snap:self.calls.append((op,snap)) or {'status':'activated'})
        self.operations={}

    def tearDown(self):
        self.gate.close()
        self.fix.stop()
        self.tmp.cleanup()

    def op(self,target='hache-miner'):
        filename=self.inbox/target/('b'*40+'.tar.gz')
        filename.parent.mkdir(exist_ok=True)
        fixture_archive(filename,target)
        op={'target':target,'commit':'b'*40,
            'archive_sha256':hashlib.sha256(filename.read_bytes()).hexdigest()}
        return {'method':'prepare',**op}

    def grant(self,plan):
        p=self.grants/(plan['plan_id']+'.json')
        p.write_text(d.compact({
            'plan_id':plan['plan_id'],'digest':plan['digest'],
            'expires_at':plan['expires_at']
        }))
        p.chmod(0o600)
        return p

    def test_rate_limit_and_root_cache_capacity(self):
        for _ in range(120):
            self.gate.charge()
        with self.assertRaisesRegex(d.Rejected,'rate_limited'):
            self.gate.charge()
        incoming=self.op()
        private=self.state/'approved-sources'
        private.mkdir()
        for i in range(8):
            (private/(format(i,'064x')+'.tar.gz')).write_bytes(b'fixture')
        with self.assertRaisesRegex(d.Rejected,'cache_full'):
            self.gate.handle(incoming)

    def test_only_fixed_targets_and_40_char_commit(self):
        for req in (
          {'method':'prepare','target':'../../tmp','commit':'b'*40,'archive_sha256':'0'*64},
          {'method':'prepare','target':'hache-miner','commit':'main','archive_sha256':'0'*64},
          {'method':'prepare','target':'hache-miner','commit':'b'*40,'archive_sha256':'evil'},
          {'method':'execute','plan_id':'../../root'},
          {'method':'capabilities','command':'sudo -i'},
        ):
            with self.assertRaises(d.Rejected):
                d.valid_request(req)
        self.assertIn('hache-miner',self.gate.handle({'method':'capabilities'})['targets'])

    def test_complete_plan_rejects_ungated_execute_and_replay(self):
        plan=self.gate.handle(self.op())
        pid=plan['plan_id']
        self.assertEqual(plan['snapshot']['repository'],'manglefurniture/HACHE-MINER')
        self.assertEqual(self.calls,[])
        with self.assertRaisesRegex(d.Rejected,'owner_authorization_required'):
            self.gate.handle({'method':'execute','plan_id':pid})
        self.grant(plan)
        result=self.gate.handle({'method':'execute','plan_id':pid})
        self.assertEqual(result['phase'],'activated')
        self.assertEqual(len(self.calls),1)
        self.assertEqual(self.gate.handle({'method':'execute','plan_id':pid}),result)
        self.assertEqual(len(self.calls),1)

    def test_altered_grant_and_target_symlink_blocked(self):
        plan=self.gate.handle(self.op('hache-base'))
        p=self.grant(plan)
        grant=json.loads(p.read_text())
        grant['digest']='0'*64
        p.write_text(json.dumps(grant))
        with self.assertRaisesRegex(d.Rejected,'grant_invalid'):
            self.gate.handle({'method':'execute','plan_id':plan['plan_id']})
        self.assertEqual(self.calls,[])
        p.write_text(d.compact({'plan_id':plan['plan_id'],
                                'digest':plan['digest'],
                                'expires_at':plan['expires_at']}))
        current=self.bb/'current'
        current.unlink()
        current.symlink_to(self.bb/'releases'/('z'*40))
        with self.assertRaises(d.Rejected):
            self.gate.handle({'method':'execute','plan_id':plan['plan_id']})
        self.assertEqual(self.calls,[])

    def test_unknown_outcome_burns_grant(self):
        plan=self.gate.handle(self.op())
        self.grant(plan)
        def failing(op,snapshot):
            self.calls.append((op,snapshot))
            raise TimeoutError('private logs must not escape')
        self.gate.deploy_fn=failing
        status=self.gate.handle({'method':'execute','plan_id':plan['plan_id']})
        self.assertEqual(status['phase'],'failed_or_unknown')
        self.assertNotIn('private logs',d.compact(status))
        self.gate.handle({'method':'execute','plan_id':plan['plan_id']})
        self.assertEqual(len(self.calls),1)

    def test_archive_integrity_and_type_rejections(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in ('../escape','/etc/passwd','nested/../../escape'):
                candidate=root/(hashlib.sha256(name.encode()).hexdigest()+'.tgz')
                with tarfile.open(candidate,'w:gz') as tar:
                    info=tarfile.TarInfo(name);info.size=1
                    tar.addfile(info,io.BytesIO(b'a'))
                with self.assertRaises(d.Rejected):
                    d.safe_archive(candidate)
            link=root/'link.tar.gz'
            with tarfile.open(link,'w:gz') as tar:
                info=tarfile.TarInfo('evil');info.type=tarfile.SYMTYPE
                info.linkname='/etc/passwd'
                tar.addfile(info)
            with self.assertRaises(d.Rejected):
                d.safe_archive(link)
        req=self.op()
        filename=self.inbox/'hache-miner'/('b'*40+'.tar.gz')
        req['archive_sha256']='0'*64
        with self.assertRaisesRegex(d.Rejected,'source_digest_mismatch'):
            self.gate.handle(req)
        self.assertFalse((self.state/'approved-sources'/('0'*64+'.tar.gz')).exists())

    def test_extraction_uses_no_archive_writes_outside_release(self):
        req=self.op('hache-base')
        archive=self.inbox/'hache-base'/('b'*40+'.tar.gz')
        with tempfile.TemporaryDirectory() as tmp:
            d.extract_fixed_archive(archive, tmp)
            self.assertTrue((Path(tmp)/'extensions/mining-operator/broker.py').exists())
            self.assertFalse((Path(tmp)/'../etc/passwd').exists())

    def test_release_symlink_nested_or_direct(self):
        self.assertEqual(d.strict_symlink_destination(
            self.rr/'current',self.rr/'releases').name,'a'*40)
        self.assertEqual(d.strict_symlink_destination(
            self.bb/'current',self.bb/'releases').name,'mining-operator')
        curr=self.rr/'current'
        curr.unlink()
        curr.symlink_to(self.root)
        with self.assertRaises(d.Rejected):
            d.strict_symlink_destination(curr,self.rr/'releases')

    def test_activate_rollback_on_failed_health(self):
        plan=self.gate.handle(self.op())
        op=plan['operation'];snapshot=plan['snapshot']
        self.gate.deploy_fn=self.gate.activate
        with patch.object(d,'run_checks'), patch.object(d,'check_financial_guard_clear'), patch.object(d,'check_health',side_effect=d.Rejected('service_unhealthy')):
            with self.assertRaises(d.Rejected):
                self.gate.activate(op,snapshot)
        self.assertEqual((self.rr/'current').resolve(),Path(snapshot['previous_release']))
        self.assertTrue((self.rr/'releases'/('b'*40)).exists())

    def test_financial_lease_blocks_activation(self):
        plan=self.gate.handle(self.op())
        with patch.object(d,'run_checks'), patch.object(d,'check_financial_guard_clear',
                               side_effect=d.Rejected('active_financial_lease_blocks_deployment')), \
             patch.object(d,'check_health') as health:
            with self.assertRaisesRegex(d.Rejected,'active_financial_lease'):
                self.gate.activate(plan['operation'],plan['snapshot'])
        health.assert_not_called()
        self.assertEqual((self.rr/'current').resolve(),Path(plan['snapshot']['previous_release']))
        self.assertFalse((self.rr/'releases'/('b'*40)).exists())

    def test_manifest_mode_keeps_executable_scripts(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive=Path(tmp)/'bundle.tar.gz'
            with tarfile.open(archive,'w:gz') as tar:
                contents={'deploy/activate.sh':(b'#!/usr/bin/env bash\\n',0o755),
                          'app/core.php':(b'<?php\\n',0o644)}
                for name,(data,mode) in contents.items():
                    item=tarfile.TarInfo(name)
                    item.size=len(data);item.mode=mode
                    tar.addfile(item,io.BytesIO(data))
            dest=Path(tmp)/'output'
            dest.mkdir()
            d.extract_fixed_archive(archive,dest)
            self.assertEqual((dest/'deploy/activate.sh').stat().st_mode & 0o777,0o755)
            self.assertEqual((dest/'app/core.php').stat().st_mode & 0o777,0o644)

    def test_activate_calls_fixed_health_only(self):
        plan=self.gate.handle(self.op('hache-base'))
        self.gate.deploy_fn=self.gate.activate
        with patch.object(d,'run_checks'),patch.object(d,'check_financial_guard_clear'),patch.object(d,'check_health') as hc:
            r=self.gate.activate(plan['operation'],plan['snapshot'])
        self.assertEqual(r['status'],'activated')
        hc.assert_called_once_with('hache-base',restart=True)


if __name__=='__main__':
    unittest.main()
