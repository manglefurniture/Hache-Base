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
SERVICE="hache-mining-operator.service"

class Rejected(Exception):
    pass

def encode(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()

def verify_ticket(ticket,secret,now):
    if type(ticket) is not dict or set(ticket)!={"payload","signature"}: raise Rejected("invalid_ticket")
    p,s=ticket["payload"],ticket["signature"]
    if type(p) is not dict or set(p)!={"domain","scope","action","duration_sec","expires_at","nonce"}: raise Rejected("invalid_fields")
    if p["domain"]!=DOMAIN or p["scope"]!=SCOPE or p["action"] not in ("enable","disable"): raise Rejected("invalid_scope")
    if type(p["duration_sec"]) is not int or p["duration_sec"]!=(MAX_SECONDS if p["action"]=="enable" else 0): raise Rejected("invalid_duration")
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
    with sqlite3.connect("file:"+str(db)+"?mode=ro",uri=True,timeout=2) as conn:
        armed=conn.execute("SELECT COUNT(*) FROM vast_leases WHERE phase='armed'").fetchone()[0]
        beat=conn.execute("SELECT completed_at FROM lease_guard_heartbeat WHERE id=1").fetchone()
    if armed or not beat or not 0<=time.time()-float(beat[0])<=90: raise Rejected("financial_guard_unhealthy")
    if subprocess.run(["/usr/bin/systemctl","restart",SERVICE],capture_output=True,timeout=25).returncode: raise Rejected("restart_failed")
    if subprocess.run(["/usr/bin/systemctl","is-active","--quiet",SERVICE],capture_output=True,timeout=8).returncode: raise Rejected("operator_unhealthy")
    return {"service":SERVICE,"status":"active"}

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
        self.count=0
        self.last=-999999
    def status(self):
        active=self.until>self.monotonic()
        return {"enabled":active,"expires_at":self.wall_until if active else None,"scope":SCOPE if active else None}
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
        if p["action"]=="enable":
            self.until=self.monotonic()+MAX_SECONDS
            self.wall_until=stamp+MAX_SECONDS
            self.count=0
            self.last=-999999
        else:
            self.until=0
            self.wall_until=0
        return self.status()
    def agent(self,request):
        if type(request) is not dict or set(request)!={"method"}: raise Rejected("invalid_method")
        if request["method"]=="status": return self.status()
        if request["method"]!="restart_operator": raise Rejected("unknown_method")
        if not self.status()["enabled"]: raise Rejected("window_off")
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
                            if type(req) is not dict or set(req)!={"ticket"}: raise Rejected("admin_schema")
                            result=window.toggle(req["ticket"])
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
