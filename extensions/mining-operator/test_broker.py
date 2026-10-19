import json
import os
from pathlib import Path
import socket
import socketserver
import tempfile
import threading
import unittest

from broker import Broker, Handler, Rejected, canonical, validate_operation
from unittest.mock import patch


@unittest.skipUnless(hasattr(os, 'getuid'), 'Broker requires Linux ownership and Unix sockets')
class BrokerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        self.grants = self.folder/'grants'
        self.grants.mkdir(mode=0o700)
        self.calls = []
        self.now = 1000
        self.fail = False
        self.broker = Broker(self.folder/'state.sqlite', self.grants, self.helper,
                             grant_owner=os.getuid() if hasattr(os, 'getuid') else 0,
                             now=lambda: self.now)

    def tearDown(self):
        self.broker.close()
        self.tmp.cleanup()

    def helper(self, mode, operation, snapshot=None):
        self.calls.append(mode)
        if mode == 'execute':
            phase = self.broker.db.execute('SELECT phase FROM plans').fetchone()[0]
            self.assertEqual(phase, 'claimed')
            if self.fail:
                raise TimeoutError('secret must never appear in client response')
            return {'status': 'accepted', 'verification_required': True}
        return {'id': operation.get('instance_id'), 'actual_status': 'running'}

    def prepare(self):
        return self.broker.handle({'method': 'prepare', 'operation':
                                  {'action': 'vast.stop', 'instance_id': '123'}})

    def grant(self, plan):
        path = self.grants/(plan['plan_id']+'.json')
        path.write_text(canonical({'plan_id': plan['plan_id'], 'digest': plan['digest'],
                                   'expires_at': plan['expires_at']}))
        path.chmod(0o600)
        return path

    def test_read_method_cannot_mutate(self):
        with self.assertRaises(Rejected):
            self.broker.handle({'method': 'query', 'operation':
                                {'action': 'vast.stop', 'instance_id': '123'}})
        self.assertEqual(self.calls, [])

    def test_no_grant_means_no_execution(self):
        plan = self.prepare()
        with self.assertRaisesRegex(Rejected, 'authorization_required'):
            self.broker.handle({'method': 'execute', 'plan_id': plan['plan_id']})
        self.assertEqual(self.calls, ['prepare'])

    def test_one_use_replay_returns_result_without_resending(self):
        plan = self.prepare()
        self.grant(plan)
        request = {'method': 'execute', 'plan_id': plan['plan_id']}
        result = self.broker.handle(request)
        self.assertEqual(result['phase'], 'submitted')
        self.assertEqual(self.broker.handle(request), result)
        self.assertEqual(self.calls.count('execute'), 1)

    def test_unknown_outcome_burns_grant(self):
        plan = self.prepare()
        self.grant(plan)
        self.fail = True
        request = {'method': 'execute', 'plan_id': plan['plan_id']}
        result = self.broker.handle(request)
        self.assertEqual(result['phase'], 'failed_or_unknown')
        self.assertNotIn('secret', canonical(result))
        self.broker.handle(request)
        self.assertEqual(self.calls.count('execute'), 1)

    def test_database_plan_tampering_rejected(self):
        plan = self.prepare()
        self.grant(plan)
        self.broker.db.execute('UPDATE plans SET operation=?',
                              (canonical({'action': 'vast.stop', 'instance_id': '999'}),))
        with self.assertRaisesRegex(Rejected, 'plan_content_changed'):
            self.broker.handle({'method': 'execute', 'plan_id': plan['plan_id']})
        self.assertNotIn('execute', self.calls)

    def test_different_digest_and_expired_plan_rejected(self):
        plan = self.prepare()
        path = self.grant(plan)
        data = json.loads(path.read_text())
        data['digest'] = '0'*64
        path.write_text(json.dumps(data))
        with self.assertRaises(Rejected):
            self.broker.handle({'method': 'execute', 'plan_id': plan['plan_id']})
        self.now += 301
        with self.assertRaisesRegex(Rejected, 'plan_expired'):
            self.broker.handle({'method': 'execute', 'plan_id': plan['plan_id']})

    @unittest.skipUnless(hasattr(os, 'getuid'), 'Linux ownership required')
    def test_mutable_grant_or_wrong_owner_rejected(self):
        plan = self.prepare()
        path = self.grant(plan)
        path.chmod(0o660)
        request = {'method': 'execute', 'plan_id': plan['plan_id']}
        with self.assertRaises(Rejected):
            self.broker.handle(request)
        path.chmod(0o600)
        self.broker.grant_owner = os.getuid()+1
        with self.assertRaises(Rejected):
            self.broker.handle(request)

    def test_extra_fields_cannot_override_bound_operation(self):
        plan = self.prepare()
        self.grant(plan)
        with self.assertRaises(Rejected):
            self.broker.handle({'method': 'execute', 'plan_id': plan['plan_id'],
                                'operation': {'action': 'vast.stop', 'instance_id': '999'}})

    def test_targets_and_financial_actions_rejected(self):
        for operation in ({'action': 'vast.destroy', 'instance_id': '123'},
                          {'action': 'vast.start', 'instance_id': '123'},
                          {'action': 'vast.start', 'instance_id': '123', 'max_hourly_usd': float('nan'), 'max_total_usd': 20, 'max_minutes': 5},
                          {'action': 'vast.start', 'instance_id': '123', 'max_hourly_usd': 4, 'max_total_usd': 20, 'max_minutes': True},
                          {'action': 'vast.status', 'instance_id': '../123'},
                          {'action': 'vast.status', 'instance_id': True},
                          {'action': 'salad.groups', 'organization': 'x/y', 'project': 'p'},
                          {'action': 'vast.search', 'gpu_name': 'RTX', 'gpu_count': True, 'max_hourly_usd': 1}):
            with self.subTest(operation=operation), self.assertRaises(Rejected):
                validate_operation(operation)


    def test_start_exact_grant_and_independent_lease_before_provider_call(self):
        op={'action':'vast.start','instance_id':'56667162','max_minutes':20,
            'max_hourly_usd':5,'max_total_usd':2}
        plan=self.broker.handle({'method':'prepare','operation':op})
        self.assertEqual(plan['snapshot']['id'],'56667162')
        self.assertNotIn('execute',self.calls)
        self.grant(plan)
        with patch('broker.arm_financial_lease',return_value={'deadline_unix':2200}) as lease:
            result=self.broker.handle({'method':'execute','plan_id':plan['plan_id']})
        self.assertEqual(result['phase'],'submitted')
        lease.assert_called_once()
        self.assertEqual(self.calls.count('execute'),1)
        self.assertEqual(result['result']['financial_lease']['deadline_unix'],2200)
        self.broker.handle({'method':'execute','plan_id':plan['plan_id']})
        self.assertEqual(self.calls.count('execute'),1)

    def test_start_no_timer_never_calls_provider_mutation(self):
        op={'action':'vast.start','instance_id':'56667162','max_minutes':20,
            'max_hourly_usd':5,'max_total_usd':2}
        plan=self.broker.handle({'method':'prepare','operation':op})
        self.grant(plan)
        with patch('broker.arm_financial_lease',side_effect=RuntimeError('timer disabled')):
            result=self.broker.handle({'method':'execute','plan_id':plan['plan_id']})
        self.assertEqual(result['phase'],'failed_or_unknown')
        self.assertNotIn('execute',self.calls)

    def test_vast_registration_requires_exact_one_use_root_grant(self):
        operation={'action':'vast.register','instance_id':'56667162'}
        plan=self.broker.handle({'method':'prepare','operation':operation})
        self.assertEqual(plan['operation'],operation)
        self.assertEqual(self.calls,['prepare'])
        with self.assertRaisesRegex(Rejected,'authorization_required'):
            self.broker.handle({'method':'execute','plan_id':plan['plan_id']})
        self.grant(plan)
        answer=self.broker.handle({'method':'execute','plan_id':plan['plan_id']})
        self.assertEqual(answer['phase'],'submitted')
        self.assertEqual(self.calls.count('execute'),1)
        again=self.broker.handle({'method':'execute','plan_id':plan['plan_id']})
        self.assertEqual(again,answer)
        self.assertEqual(self.calls.count('execute'),1)

    def test_vast_inspect_is_read_only(self):
        value=self.broker.handle({'method':'query','operation':
                    {'action':'vast.inspect','instance_id':'56667162'}})
        self.assertEqual(value['id'],'56667162')
        self.assertEqual(self.calls,['query'])
        with self.assertRaisesRegex(Rejected,'query_cannot_mutate'):
            self.broker.handle({'method':'query','operation':
                    {'action':'vast.register','instance_id':'56667162'}})

    def test_provision_three_phases_require_exact_one_use_root_grants(self):
        for step in ('stage','configure','apply'):
            with self.subTest(step=step):
                self.calls.clear()
                op={'action':'vast.provision','instance_id':'56667162',
                    'release_commit':'a'*40,'step':step}
                plan=self.broker.handle({'method':'prepare','operation':op})
                with self.assertRaisesRegex(Rejected,'authorization_required'):
                    self.broker.handle({'method':'execute','plan_id':plan['plan_id']})
                self.assertEqual(self.calls,['prepare'])
                self.grant(plan)
                answer=self.broker.handle({'method':'execute','plan_id':plan['plan_id']})
                self.assertEqual(answer['phase'],'submitted')
                self.assertEqual(self.calls.count('execute'),1)
                self.assertEqual(self.broker.handle({'method':'execute','plan_id':plan['plan_id']}),answer)
                self.assertEqual(self.calls.count('execute'),1)
        for change in [
            {'action':'vast.provision','instance_id':'56667162','release_commit':'main','step':'apply'},
            {'action':'vast.provision','instance_id':'56667162','release_commit':'a'*40,'step':'restart'},
            {'action':'vast.provision','instance_id':'56667162','release_commit':'a'*40,'step':True},
            {'action':'vast.provision','instance_id':'../56667162','release_commit':'a'*40,'step':'stage'},
            {'action':'vast.provision','instance_id':'56667162','release_commit':'a'*40,'step':'stage','wallet':'fake'},
        ]:
            with self.subTest(change=change),self.assertRaises(Rejected):
                validate_operation(change)

    def test_rate_limit_fails_closed(self):
        for _ in range(120):
            self.broker.charge()
        with self.assertRaisesRegex(Rejected, 'rate_limited'):
            self.broker.charge()


@unittest.skipUnless(hasattr(socket, 'SO_PEERCRED'), 'Linux peer credentials required')
class PeerTests(unittest.TestCase):
    def test_other_uid_rejected_before_dispatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp)/'operator.sock')
            server = socketserver.UnixStreamServer(path, Handler)
            server.allowed_uid = os.getuid()+1
            thread = threading.Thread(target=server.handle_request)
            thread.start()
            try:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                    client.settimeout(3)
                    client.connect(path)
                    result = json.loads(client.makefile('rb').readline())
                    self.assertEqual(result, {'ok': False, 'error': 'peer_not_authorized'})
            finally:
                thread.join(timeout=3)
                server.server_close()


if __name__ == '__main__':
    unittest.main()
