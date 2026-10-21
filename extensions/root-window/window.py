"""Fail-closed root capability window: no shell, no sudo, no dynamic service names."""
import argparse
import hashlib
import hmac
import json
import os
import selectors
import socket
import sqlite3
import stat
import struct
import subprocess
import time
from pathlib import Path

DOMAIN="hache-root-window/v1"
SCOPE="restart_operator"
MAX_SECONDS=600
FULL_SCOPE="full_root"
MAX_ROOT_SECONDS=86400
ROOT_HELPER="/usr/local/sbin/hache-gpt-sudo-window"
ROOT_STATE="/var/lib/hache-gpt-sudo-window/current"
ROOT_SUDOERS="/etc/sudoers.d/91-hache-gpt-agent-window"
SERVICE="hache-mining-operator.service"

class Rejected(Exception):
    pass

def encode(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()

def verify_ticket(ticket,secret,now):
    if type(ticket) is not dict or set(ticket)!={"payload","signature"}: raise Rejected("invalid_ticket")
    p,s=ticket["payload"],ticket["signature"]
    if type(p) is not dict or set(p)!={"domain","scope","action","duration_sec","expires_at","nonce"}: raise Rejected("invalid_fields")
    if p["domain"]!=DOMAIN or p["scope"] not in (SCOPE,FULL_SCOPE) or p["action"] not in ("enable","disable"): raise Rejected("invalid_scope")
    sec=p["duration_sec"]
    if type(sec) is not int: raise Rejected("invalid_duration")
    if p["action"]=="disable":
        if sec!=0: raise Rejected("invalid_duration")
    elif p["scope"]==SCOPE:
        if sec!=MAX_SECONDS: raise Rejected("invalid_duration")
    elif sec<60 or sec>MAX_ROOT_SECONDS or sec%60:
        raise Rejected("invalid_duration")
    if type(p["expires_at"]) is not int or not now<p["expires_at"]<=now+30: raise Rejected("expired")
    if type(p["nonce"]) is not str or not 24<=len(p["nonce"])<=80 or not all(c.isalnum() or c in "-_" for c in p["nonce"]): raise Rejected("invalid_nonce")
    if type(s) is not str or len(s)!=64 or not hmac.compare_digest(s,hmac.new(secret,encode(p),hashlib.sha256).hexdigest()): raise Rejected("invalid_signature")
    return p

def safe_config(path):
    fd=os.open(path,os.O_RDONLY|getattr(os,"O_NOFOLLOW",0))
    with os.fdopen(fd) as f:
        st=os.fstat(f.fileno())
        if not stat.S_ISREG(st.st_mode) or st.st_uid!=0 or st.st_mode&0o077: raise Rejected("untrusted_config")
        cfg=json.load(f)
    keys={"database","secret_hex","admin_uid","agent_uid","admin_gid","agent_gid","admin_socket","agent_socket"}
    if set(cfg)!=keys: raise Rejected("config_schema")
    try: secret=bytes.fromhex(cfg["secret_hex"])
    except (ValueError,TypeError) as exc: raise Rejected("invalid_secret") from exc
    if len(secret)!=32: raise Rejected("invalid_secret")
    for key in ("admin_uid","agent_uid","admin_gid","agent_gid"):
        if type(cfg[key]) is not int or cfg[key]<=0: raise Rejected("invalid_identity")
    for key,prefix in (("database","/var/lib/hache-root-window/"),("admin_socket","/run/hache-root-window/"),("agent_socket","/run/hache-root-window/")):
        if type(cfg[key]) is not str or not cfg[key].startswith(prefix): raise Rejected("invalid_path")
    if cfg["admin_socket"]==cfg["agent_socket"] or cfg["admin_uid"]==cfg["agent_uid"]: raise Rejected("identity_separation")
    return cfg,secret


def restart_with_lease_lock(db, *, runner=None, clock=None):
    """Serialize with arm()/arm_rental() through their shared SQLite writer lock."""
    runner = runner or subprocess.run
    clock = clock or time.time
    conn = None
    try:
        conn = sqlite3.connect("file:"+str(db)+"?mode=rw",uri=True,timeout=2,isolation_level=None)
        conn.execute("BEGIN IMMEDIATE")
        armed = conn.execute("SELECT COUNT(*) FROM vast_leases WHERE phase='armed'").fetchone()[0]
        beat = conn.execute("SELECT completed_at FROM lease_guard_heartbeat WHERE id=1").fetchone()
        if armed or not beat or not 0 <= clock()-float(beat[0]) <= 90:
            raise Rejected("financial_guard_unhealthy")
        if runner(["/usr/bin/systemctl","restart",SERVICE],capture_output=True,timeout=25).returncode:
            raise Rejected("restart_failed")
        if runner(["/usr/bin/systemctl","is-active","--quiet",SERVICE],capture_output=True,timeout=8).returncode:
            raise Rejected("operator_unhealthy")
        return {"service":SERVICE,"status":"active"}
    except (sqlite3.Error,OSError,ValueError,KeyError,TypeError,subprocess.TimeoutExpired) as exc:
        raise Rejected("financial_guard_unavailable") from exc
    finally:
        if conn is not None:
            try:
                if conn.in_transaction:
                    conn.rollback()
            finally:
                conn.close()

def safe_restart():
    # Never interrupt the financial guardian while a Vast financial lease is armed.
    path="/etc/hache-mining-operator/config.json"
    fd=os.open(path,os.O_RDONLY|getattr(os,"O_NOFOLLOW",0))
    with os.fdopen(fd) as f:
        st=os.fstat(f.fileno())
        if not stat.S_ISREG(st.st_mode) or st.st_uid!=0 or st.st_mode&0o022: raise Rejected("untrusted_financial_config")
        cfg=json.load(f)
    db=Path(cfg["database"])
    if not db.is_absolute() or not db.is_relative_to("/var/lib/hache-mining-operator") or db.is_symlink(): raise Rejected("untrusted_financial_db")
    return restart_with_lease_lock(db)



def _sudo_expires_at():
    """Only root-owned state controls browser display after daemon restart."""
    try:
        st=os.stat(ROOT_STATE,follow_symlinks=False)
        if not stat.S_ISREG(st.st_mode) or st.st_uid!=0 or st.st_mode&0o077:
            return None
        st2=os.stat(ROOT_SUDOERS,follow_symlinks=False)
        if not stat.S_ISREG(st2.st_mode) or st2.st_uid!=0 or st2.st_mode&0o022:
            return None
        with open(ROOT_STATE,encoding="ascii") as f:
            parts=f.read(128).split()
        if len(parts)!=2 or len(parts[0])!=24 or any(c not in "0123456789abcdef" for c in parts[0]):
            return None
        expiry=int(parts[1])
        if not time.time()<expiry<=time.time()+MAX_ROOT_SECONDS+90:
            return None
        return expiry
    except (OSError,ValueError):
        return None

def _root_helper(action,minutes=0):
    args=[ROOT_HELPER,action]+([str(minutes)] if action=="start" else [])
    p=subprocess.run(args,capture_output=True,timeout=8,check=False)
    if p.returncode:
        raise Rejected("root_helper_failed")
    return True

class Window:
    """In-memory grants disappear on daemon restart; nonce/audit persist as root."""
    def __init__(self,path,secret,now=None,monotonic=None,execute=None):
        if len(secret)!=32: raise ValueError("secret_length")
        self.secret=secret
        self.now=now or (lambda: int(time.time()))
        self.monotonic=monotonic or time.monotonic
        self.execute=execute or safe_restart
        self.db=sqlite3.connect(path,isolation_level=None,timeout=5)
        self.db.execute("CREATE TABLE IF NOT EXISTS used(nonce TEXT PRIMARY KEY,expires INTEGER NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,at INTEGER NOT NULL,actor TEXT NOT NULL,action TEXT NOT NULL,outcome TEXT NOT NULL)")
        self.until=0
        self.wall_until=0
        self.scope=None
        self.count=0
        self.last=-999999
    def status(self):
        root_exp=_sudo_expires_at()
        if root_exp is not None:
            self.scope=FULL_SCOPE
            self.wall_until=root_exp
            self.until=self.monotonic()+max(0,root_exp-self.now())
        elif self.scope==FULL_SCOPE:
            self.scope=None
            self.until=0
            self.wall_until=0
        active=self.until>self.monotonic()
        if not active: self.scope=None
        return {"enabled":active,"expires_at":self.wall_until if active else None,
                "scope":self.scope if active else None}
    def toggle(self,ticket):
        stamp=self.now()
        p=verify_ticket(ticket,self.secret,stamp)
        try:
            self.db.execute("BEGIN IMMEDIATE")
            self.db.execute("DELETE FROM used WHERE expires<?",(stamp-300,))
            self.db.execute("INSERT INTO used VALUES (?,?)",(p["nonce"],p["expires_at"]))
            self.db.execute("INSERT INTO audit(at,actor,action,outcome) VALUES (?,?,?,?)",(stamp,"owner-passkey",p["action"],"approved"))
            self.db.commit()
        except sqlite3.IntegrityError as exc:
            self.db.rollback()
            raise Rejected("replay") from exc
        except Exception:
            self.db.rollback()
            raise
        try:
            # Any owner action cancels an earlier full-root sudo grant.
            if p["scope"]==FULL_SCOPE or self.scope==FULL_SCOPE or _sudo_expires_at() is not None:
                _root_helper("stop")
            if p["action"]=="enable":
                if p["scope"]==FULL_SCOPE:
                    _root_helper("start",p["duration_sec"]//60)
                self.until=self.monotonic()+p["duration_sec"]
                self.wall_until=stamp+p["duration_sec"]
                self.scope=p["scope"]
                self.count=0
                self.last=-999999
            else:
                self.until=0
                self.wall_until=0
                self.scope=None
        except Exception:
            try: _root_helper("stop")
            except Exception: pass
            self.until=0
            self.wall_until=0
            self.scope=None
            raise Rejected("root_grant_failed_closed") from None
        return self.status()
    def agent(self,request):
        if type(request) is not dict or set(request)!={"method"}: raise Rejected("invalid_method")
        if request["method"]=="status": return self.status()
        if request["method"]!="restart_operator": raise Rejected("unknown_method")
        if not self.status()["enabled"] or self.scope!=SCOPE: raise Rejected("window_off")
        if self.count>=3 or self.monotonic()-self.last<60: raise Rejected("rate_limit")
        self.count+=1
        self.last=self.monotonic()
        try:
            result=self.execute()
            self.db.execute("INSERT INTO audit(at,actor,action,outcome) VALUES (?,?,?,?)",(self.now(),"gpt-agent","restart_operator","completed"))
            return result
        except Exception:
            self.db.execute("INSERT INTO audit(at,actor,action,outcome) VALUES (?,?,?,?)",(self.now(),"gpt-agent","restart_operator","failed_or_unknown"))
            raise Rejected("operation_unverified") from None
    def close(self): self.db.close()

def main(path):
    if os.geteuid()!=0: raise RuntimeError("root_required")
    cfg,secret=safe_config(path)
    window=Window(cfg["database"],secret)
    sel=selectors.DefaultSelector()
    bound=[]
    try:
        for role in ("admin","agent"):
            path=cfg[role+"_socket"]
            if os.path.lexists(path): raise RuntimeError("socket_already_exists")
            s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
            s.bind(path)
            os.chown(path,0,cfg[role+"_gid"])
            os.chmod(path,0o660)
            s.listen(4)
            sel.register(s,selectors.EVENT_READ,role)
            bound.append((s,path))
        while True:
            for ready,_ in sel.select():
                role=ready.data
                conn,_=ready.fileobj.accept()
                with conn:
                    conn.settimeout(5)
                    try:
                        pid,uid,gid=struct.unpack("3i",conn.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
                        if uid!=cfg[role+"_uid"]: raise Rejected("peer")
                        raw=b""
                        while len(raw)<=4096 and b"\n" not in raw:
                            chunk=conn.recv(1024)
                            if not chunk: break
                            raw+=chunk
                        if len(raw)>4096 or not raw.endswith(b"\n"): raise Rejected("frame")
                        req=json.loads(raw)
                        if role=="admin":
                            if req=={"method":"status"}: result=window.status()
                            elif type(req) is dict and set(req)=={"ticket"}: result=window.toggle(req["ticket"])
                            else: raise Rejected("admin_schema")
                        else:
                            result=window.agent(req)
                        outcome={"ok":True,"result":result}
                    except Exception:
                        outcome={"ok":False,"error":"request_denied"}
                    conn.sendall(encode(outcome)+b"\n")
    finally:
        sel.close()
        for sock,path in bound:
            sock.close()
            os.unlink(path)
        window.close()

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--config",required=True)
    main(parser.parse_args().config)
