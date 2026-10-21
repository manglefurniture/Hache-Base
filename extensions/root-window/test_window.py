import hashlib
import hmac
import os
import sqlite3
from types import SimpleNamespace
import tempfile
import unittest
from window import Window,Rejected,DOMAIN,SCOPE,MAX_SECONDS,encode,restart_with_lease_lock

SECRET=b"test-secret-32-bytes-for-gate-00"
class WindowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.now=100000
        self.mono=1000
        self.runs=0
        def op():
            self.runs+=1
            return {"status":"ok"}
        self.path=os.path.join(self.tmp.name,"state.sqlite")
        self.w=Window(self.path,SECRET,now=lambda:self.now,
                      monotonic=lambda:self.mono,execute=op)
    def tearDown(self):
        self.w.close()
        self.tmp.cleanup()
    def ticket(self,action="enable",**kwargs):
        p={"domain":DOMAIN,"scope":SCOPE,"action":action,"duration_sec":MAX_SECONDS if action=="enable" else 0,"expires_at":self.now+20,"nonce":"abcdefghijklmnopqrstuvwx12345678"}
        p.update(kwargs)
        return {"payload":p,"signature":hmac.new(SECRET,encode(p),hashlib.sha256).hexdigest()}
    def test_off_by_default_and_restart(self):
        self.assertFalse(self.w.status()["enabled"])
        with self.assertRaises(Rejected): self.w.agent({"method":"restart_operator"})
        self.w.toggle(self.ticket())
        self.w.agent({"method":"restart_operator"})
        self.assertEqual(self.runs,1)
        self.mono+=601
        self.assertFalse(self.w.status()["enabled"])
        other=Window(self.path,SECRET,now=lambda:self.now,monotonic=lambda:1000)
        self.assertFalse(other.status()["enabled"])
        other.close()
    def test_replay_and_revocation(self):
        ticket=self.ticket()
        self.w.toggle(ticket)
        with self.assertRaises(Rejected): self.w.toggle(ticket)
        self.w.toggle(self.ticket("disable",nonce="12345678abcdefghijklmnopqrstuvwx"))
        self.assertFalse(self.w.status()["enabled"])
    def test_scope_and_signature(self):
        for params in ({"scope":"arbitrary_shell"},{"duration_sec":601},{"expires_at":self.now+60}):
            with self.assertRaises(Rejected): self.w.toggle(self.ticket(**params))
        t=self.ticket()
        t["signature"]="f"*64
        with self.assertRaises(Rejected): self.w.toggle(t)
    def test_bounded_operations(self):
        self.w.toggle(self.ticket())
        for req in ({"method":"exec","command":"whoami"},{"method":"restart_operator","service":"mariadb"},{"method":"status","sudo":True}):
            with self.assertRaises(Rejected): self.w.agent(req)
        self.w.agent({"method":"restart_operator"})
        with self.assertRaises(Rejected): self.w.agent({"method":"restart_operator"})
        self.mono+=61
        self.w.agent({"method":"restart_operator"})
        self.mono+=61
        self.w.agent({"method":"restart_operator"})
        self.mono+=61
        with self.assertRaises(Rejected): self.w.agent({"method":"restart_operator"})
        self.assertEqual(self.runs,3)
    def test_failed_action_counts(self):
        self.w.toggle(self.ticket())
        self.w.execute=lambda: (_ for _ in ()).throw(OSError("error"))
        with self.assertRaises(Rejected): self.w.agent({"method":"restart_operator"})
        self.assertEqual(self.w.count,1)
        self.assertEqual(self.w.db.execute("SELECT outcome FROM audit ORDER BY id DESC LIMIT 1").fetchone()[0],"failed_or_unknown")

class FinancialConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=os.path.join(self.tmp.name,"operator.sqlite")
        self.db=sqlite3.connect(self.path,isolation_level=None)
        self.db.execute("CREATE TABLE vast_leases(phase TEXT NOT NULL)")
        self.db.execute("CREATE TABLE lease_guard_heartbeat(id INTEGER PRIMARY KEY,completed_at REAL NOT NULL)")
        self.db.execute("INSERT INTO lease_guard_heartbeat VALUES(1,1000)")
    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()
    def test_arm_cannot_commit_between_check_and_restart(self):
        calls=[]
        def run(args,**kwargs):
            calls.append(args)
            with sqlite3.connect(self.path,timeout=0,isolation_level=None) as second:
                with self.assertRaises(sqlite3.OperationalError):
                    second.execute("BEGIN IMMEDIATE")
            return SimpleNamespace(returncode=0)
        result=restart_with_lease_lock(self.path,runner=run,clock=lambda:1001)
        self.assertEqual(result["status"],"active")
        self.assertEqual(len(calls),2)
        # Lock must be released on success.
        self.db.execute("BEGIN IMMEDIATE")
        self.db.rollback()
    def test_active_lease_denies_before_restart(self):
        self.db.execute("INSERT INTO vast_leases VALUES('armed')")
        calls=[]
        with self.assertRaises(Rejected):
            restart_with_lease_lock(self.path,runner=lambda *a,**k:calls.append(a),
                                    clock=lambda:1001)
        self.assertEqual(calls,[])
    def test_stale_heartbeat_denies(self):
        calls=[]
        with self.assertRaises(Rejected):
            restart_with_lease_lock(self.path,runner=lambda *a,**k:calls.append(a),
                                    clock=lambda:1200)
        self.assertEqual(calls,[])

if __name__=="__main__":unittest.main()
