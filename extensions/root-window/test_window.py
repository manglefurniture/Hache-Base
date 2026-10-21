import hashlib
import hmac
import os
import tempfile
import unittest
from window import Window,Rejected,DOMAIN,SCOPE,MAX_SECONDS,encode

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
if __name__=="__main__":unittest.main()
