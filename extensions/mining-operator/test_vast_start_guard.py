import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from vast_start_guard import install_tables, arm, check_expired, LeaseError


def operation(**overrides):
    value={'action':'vast.start','instance_id':'56667162','max_minutes':20,
           'max_hourly_usd':5.0,'max_total_usd':2.0}
    value.update(overrides)
    return value


def snapshot():
    return {'id':56667162,'machine_id':151300,'host_id':467312,
            'actual_status':'exited','intended_status':'stopped',
            'dph_total':4.29,'num_gpus':8,'estimated_cost_cents':143}


class FinancialLeaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=sqlite3.connect(str(Path(self.tmp.name)/'state.sqlite'),
                                isolation_level=None)
        install_tables(self.db)
        self.db.execute('INSERT INTO lease_guard_heartbeat VALUES(1,1000)')
        self.events=[]

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def arm(self, **options):
        return arm(self.db,'a'*32,operation(**options),snapshot(),now=1010,
                   timer_check=lambda:True)

    def test_refuse_missing_timer(self):
        with self.assertRaisesRegex(LeaseError,'timer_inactive'):
            arm(self.db,'a'*32,operation(),snapshot(),now=1010,
                timer_check=lambda:False)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM vast_leases').fetchone()[0],0)

    def test_refuse_stale_heartbeat(self):
        with self.assertRaisesRegex(LeaseError,'supervisor_unhealthy'):
            arm(self.db,'a'*32,operation(),snapshot(),now=1100,
                timer_check=lambda:True)

    def test_lease_is_durable_before_any_provider_mutation(self):
        result=self.arm()
        self.assertEqual(result['deadline_unix'],2210)
        row=self.db.execute('SELECT phase,instance_id,deadline FROM vast_leases').fetchone()
        self.assertEqual(row,('armed','56667162',2210))
        with self.assertRaisesRegex(LeaseError,'active_financial_lease'):
            arm(self.db,'b'*32,operation(instance_id='2'),snapshot(),
                now=1011,timer_check=lambda:True)

    def test_deadline_cannot_be_omitted(self):
        for minutes in (0,1441,True,1.5):
            with self.subTest(minutes=minutes),self.assertRaises(LeaseError):
                self.arm(max_minutes=minutes)

    def test_stop_not_called_early(self):
        self.arm()
        def helper(*a):
            raise AssertionError('No provider mutation before deadline')
        result=check_expired(self.db,helper,now=2209)
        self.assertEqual(result['active'],1)

    def test_expiry_retry_until_confirmed_stopped(self):
        self.arm()
        def submitted(mode,op,snap):
            self.events.append((mode,op['instance_id'],snap['machine_id']))
            return {'status':'accepted','verification_required':True}
        result=check_expired(self.db,submitted,now=2210)
        self.assertEqual(result['stop_requested'],1)
        self.assertEqual(result['active'],1)
        self.assertEqual(self.events,[('guard_stop','56667162',151300)])
        def confirmed(mode,op,snap):
            return {'status':'already_stopped','provider_mutation_sent':False}
        answer=check_expired(self.db,confirmed,now=2240)
        self.assertEqual(answer['closed'],1)
        self.assertEqual(answer['active'],0)
        check_expired(self.db,lambda *a:self.fail('Would re-stop a closed lease'),now=2270)

    def test_failed_provider_stop_remains_armed_and_prevents_new_start(self):
        self.arm()
        def failed(*a):
            raise RuntimeError('provider timeout with sensitive information')
        with self.assertRaisesRegex(LeaseError,'financial_stop_unconfirmed'):
            check_expired(self.db,failed,now=2210)
        phase=self.db.execute('SELECT phase,last_outcome FROM vast_leases').fetchone()
        self.assertEqual(phase,('armed','verification_required'))
        with self.assertRaises(LeaseError):
            arm(self.db,'b'*32,operation(instance_id='2'),snapshot(),
                now=2211,timer_check=lambda:True)

    def test_closed_lease_allows_later_plan(self):
        self.arm()
        check_expired(self.db,lambda *a:{'status':'already_stopped'},now=2210)
        self.db.execute('INSERT INTO lease_guard_heartbeat(id,completed_at) '
                        'VALUES(1,2300) ON CONFLICT(id) DO UPDATE SET completed_at=2300')
        result=arm(self.db,'b'*32,operation(instance_id='2'),snapshot(),
                   now=2301,timer_check=lambda:True)
        self.assertEqual(result['deadline_unix'],3501)


if __name__=='__main__':
    unittest.main()
