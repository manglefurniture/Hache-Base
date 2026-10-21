#!/usr/bin/env bash
# Root-only, opt-in, fail-closed upgrade for SQLGuard root-window browser.
# Never changes MariaDB privileges, mining operator, root permissions or Vast.
set -Eeuo pipefail
if [[ "$EUID" != 0 || "$#" != 2 ]]; then
  echo "ROOT_REQUIRED: install-sqlguard-web.sh MERGED_SHA40 CLEAN_GIT_CHECKOUT" >&2
  exit 2
fi
SHA="$1"; REPO="$(realpath -- "$2")"
[[ "$SHA" =~ ^[a-f0-9]{40}$ && -d "$REPO/.git" ]] || exit 2
[[ "$(git -C "$REPO" rev-parse HEAD)" == "$SHA" ]] || { echo COMMIT_MISMATCH >&2; exit 2; }
[[ -z "$(git -C "$REPO" status --porcelain --untracked-files=all)" ]] || { echo DIRTY_SOURCE >&2; exit 2; }
git -C "$REPO" merge-base --is-ancestor "$SHA" origin/main ||
  { echo UNMERGED_SOURCE >&2; exit 2; }
ORIGIN="$(git -C "$REPO" remote get-url origin)"
[[ "$ORIGIN" == https://github.com/manglefurniture/Hache-Base.git ||
   "$ORIGIN" == https://github.com/manglefurniture/Hache-Base ]] || { echo INVALID_ORIGIN >&2; exit 2; }
SRC="$REPO/extensions/sql-guard"
ROOTSRC="$REPO/extensions/root-window/deploy"
VHOST="$ROOTSRC/nginx/aprobaciones-root-window-only.conf.example"
for f in "$SRC/approval_web.py" "$SRC/passkey_gateway.py" "$SRC/static/root_window.js" \
  "$SRC/templates/root_window.html" "$ROOTSRC/test_web_rollout.py" "$VHOST"; do
  [[ -f "$f" && ! -L "$f" ]] || { echo MISSING_REVIEWED_FILE >&2; exit 2; }
done
[[ -z "$(find "$SRC" -type l -print -quit)" ]] || { echo UNSAFE_SOURCE_SYMLINK >&2; exit 2; }

ROOTCONFIG=/etc/hache-root-window/config.json
ENVFILE=/etc/sqlguard/approval.env
DBROOT=/var/lib/sqlguard
APPROOT=/opt/sqlguard
NGINX=/etc/nginx/sites-available/aprobaciones.hacheinteractive.com
OWNER_PASS=/root/hache-root-window-owner-password
systemctl is-active --quiet hache-root-window.service || { echo WINDOW_NOT_READY >&2; exit 2; }
for f in "$ROOTCONFIG" "$ENVFILE" "$NGINX"; do
  [[ -f "$f" && ! -L "$f" ]] || { echo REQUIRED_CONFIG_MISSING >&2; exit 2; }
done
[[ "$(stat -c '%u:%g:%a' "$ROOTCONFIG")" == 0:0:600 ]] || exit 2
[[ "$(stat -c '%u:%g:%a' "$ENVFILE")" == 0:0:600 ]] || { echo UNSAFE_SQLGUARD_ENV >&2; exit 2; }

# A registered owner passkey must exist in the current isolated SQLGuard DB.
# This never reads credential material, only a count.
python3 - "$ENVFILE" <<'PY'
import pathlib,sqlite3,sys
values={}
for line in pathlib.Path(sys.argv[1]).read_text().splitlines():
    if "=" in line and not line.lstrip().startswith("#"):
        key,val=line.split("=",1)
        values[key.strip()]=val.strip().strip('"').strip("'")
p=pathlib.Path(values.get("SQLGUARD_DB_PATH",""))
if not p.is_absolute() or not p.is_relative_to("/var/lib/sqlguard"):
    raise SystemExit("UNSAFE_SQLGUARD_DB_PATH")
with sqlite3.connect("file:"+str(p)+"?mode=ro",uri=True) as db:
    count=db.execute("SELECT COUNT(*) FROM passkeys").fetchone()[0]
if count!=1:
    raise SystemExit("PASSKEY_COUNT_NOT_ONE")
print("REGISTERED_OWNER_PASSKEY_OK")
PY

# Check tests using the existing SQLGuard virtualenv, not by installing packages.
(cd "$SRC" && /opt/sqlguard/venv/bin/python -m unittest -q test_root_window_approval.py test_passkey_gateway.py test_approval_web.py)
(cd "$ROOTSRC" && /usr/bin/python3 -m unittest -q test_web_rollout.py)
bash -n "$ROOTSRC/install-sqlguard-web.sh"

RELEASE="$APPROOT/releases/$SHA"
[[ ! -e "$RELEASE" && ! -L "$RELEASE" ]] || { echo RELEASE_EXISTS >&2; exit 2; }
PREVIOUS="$(readlink -f "$APPROOT/current" 2>/dev/null || true)"
WAS_ACTIVE=0
WAS_ENABLED=0
systemctl is-active --quiet sqlguard-approval.service && WAS_ACTIVE=1 || true
systemctl is-enabled --quiet sqlguard-approval.service && WAS_ENABLED=1 || true
BACKUP="$(mktemp -d /root/sqlguard-window-rollback.XXXXXXXX)"
SUCCESS=0; SWITCHED=0; ENV_CHANGED=0; NGINX_CHANGED=0
rollback(){
  local rc=$?
  [[ "$SUCCESS" == 1 ]] && { rm -rf "$BACKUP"; return 0; }
  set +e
  if [[ "$NGINX_CHANGED" == 1 ]]; then
     install -o root -g root -m 0644 "$BACKUP/nginx.conf" "$NGINX"
     nginx -t && systemctl reload nginx
  fi
  if [[ "$SWITCHED" == 1 ]]; then
     systemctl stop sqlguard-approval.service
     if [[ -n "$PREVIOUS" && -d "$PREVIOUS" ]]; then
        ln -s "$PREVIOUS" "$APPROOT/.rollback-$SHA"
        mv -Tf "$APPROOT/.rollback-$SHA" "$APPROOT/current"
     fi
  fi
  if [[ "$ENV_CHANGED" == 1 ]]; then
     install -o root -g root -m 0600 "$BACKUP/approval.env" "$ENVFILE"
  fi
  if [[ "$SWITCHED" == 1 ]]; then
     if [[ "$WAS_ENABLED" == 0 ]]; then
        systemctl disable sqlguard-approval.service >/dev/null 2>&1
     fi
     if [[ "$WAS_ACTIVE" == 1 ]]; then
        systemctl restart sqlguard-approval.service >/dev/null 2>&1
     fi
  fi
  if [[ -d "$RELEASE" && "$(readlink -f "$APPROOT/current" 2>/dev/null)" != "$RELEASE" ]]; then
     rm -rf "$RELEASE"
  fi
  rm -rf "$BACKUP"
  return "$rc"
}
trap rollback EXIT

install -o root -g root -m 0644 "$NGINX" "$BACKUP/nginx.conf"
install -o root -g root -m 0600 "$ENVFILE" "$BACKUP/approval.env"

# The password is generated exclusively on the VPS. Never paste it in chat.
# It is independent of the registered WebAuthn passkey.
if [[ ! -e "$OWNER_PASS" ]]; then
  python3 - "$OWNER_PASS" <<'PY'
import os,secrets,sys
fd=os.open(sys.argv[1],os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
with os.fdopen(fd,"w") as f:
    f.write(secrets.token_urlsafe(36)+"\n")
PY
fi
[[ -f "$OWNER_PASS" && ! -L "$OWNER_PASS" &&
   "$(stat -c '%u:%g:%a' "$OWNER_PASS")" == 0:0:600 ]] || exit 2

# Atomic root-only env update; never log password, signing key or API credentials.
python3 - "$ROOTCONFIG" "$ENVFILE" "$OWNER_PASS" <<'PY'
import hashlib,json,os,pathlib,stat,sys,tempfile
root,env,pw=map(pathlib.Path,sys.argv[1:])
settings=json.loads(root.read_text())
key=settings["secret_hex"]
assert len(key)==64 and all(c in "0123456789abcdef" for c in key)
owner=pw.read_text().strip()
assert len(owner)>=32
lines=env.read_text().splitlines()
reserved={"SQLGUARD_ROOT_WINDOW_KEY_HEX","SQLGUARD_ROOT_WINDOW_SOCKET","SQLGUARD_ROOT_WINDOW_OWNER_AUTH_SHA256"}
lines=[line for line in lines if not (line.split("=",1)[0].strip() in reserved)]
lines.extend([
    "SQLGUARD_ROOT_WINDOW_KEY_HEX="+key,
    "SQLGUARD_ROOT_WINDOW_SOCKET=/run/hache-root-window/admin.sock",
    "SQLGUARD_ROOT_WINDOW_OWNER_AUTH_SHA256="+hashlib.sha256(owner.encode()).hexdigest()
])
fd,p=tempfile.mkstemp(prefix=".sqlguard-env-",dir=str(env.parent))
try:
    os.fchmod(fd,0o600)
    with os.fdopen(fd,"w") as dest:
        dest.write("\n".join(lines)+"\n")
        dest.flush()
        os.fsync(dest.fileno())
    os.replace(p,env)
finally:
    if os.path.exists(p): os.unlink(p)
PY
ENV_CHANGED=1

# Extract ONLY Git-tracked content from the exact commit. Never copy
# ignored .env/key/pem/untracked files from a local checkout.
install -d -o root -g root -m 0755 "$RELEASE"
python3 - "$REPO" "$SHA" "$RELEASE" <<'PY'
import io,os,pathlib,subprocess,sys,tarfile
repo,sha,release=sys.argv[1:]
archive=subprocess.run(
    ["git","-C",repo,"archive","--format=tar",sha,"extensions/sql-guard/"],
    stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True,timeout=30).stdout
dest=pathlib.Path(release)
total=0
with tarfile.open(fileobj=io.BytesIO(archive),mode="r:") as tar:
    members=tar.getmembers()
    if not members or len(members)>150:
        raise SystemExit("UNEXPECTED_ARCHIVE_ENTRIES")
    names=set()
    for member in members:
        path=pathlib.PurePosixPath(member.name)
        parts=path.parts
        if member.name in names:
            raise SystemExit("DUPLICATE_TRACKED_ENTRY")
        if parts==("extensions",) and member.isdir():
            names.add(member.name)
            (dest/"extensions").mkdir(parents=True,exist_ok=True,mode=0o755)
            continue
        if (len(parts)<2 or parts[:2]!=("extensions","sql-guard")
            or ".." in parts or "." in parts or member.name.startswith("/")
            or not (member.isfile() or member.isdir())):
            raise SystemExit("UNSAFE_TRACKED_ENTRY")
        names.add(member.name)
        total+=member.size
        if total>3_000_000:
            raise SystemExit("OVERSIZED_RELEASE")
        target=dest.joinpath(*parts)
        if member.isdir():
            target.mkdir(parents=True,exist_ok=True,mode=0o755)
        else:
            target.parent.mkdir(parents=True,exist_ok=True,mode=0o755)
            with open(target,"xb") as stream:
                stream.write(tar.extractfile(member).read())
            target.chmod(0o644)
required=(
    "extensions/sql-guard/approval_web.py",
    "extensions/sql-guard/passkey_gateway.py",
    "extensions/sql-guard/templates/root_window.html",
    "extensions/sql-guard/static/root_window.js",
)
if not all((dest/name).is_file() for name in required):
    raise SystemExit("INCOMPLETE_TRACKED_RELEASE")
PY
chown -R root:root "$RELEASE"
find "$RELEASE" -type d -exec chmod 0755 {} +
find "$RELEASE" -type f -exec chmod 0644 {} +
ln -s "$RELEASE" "$APPROOT/.next-$SHA"
mv -Tf "$APPROOT/.next-$SHA" "$APPROOT/current"
SWITCHED=1
systemctl enable --now sqlguard-approval.service
systemctl restart sqlguard-approval.service

# Root window backend proves OFF; frontend must demand owner auth.
READY=0
for attempt in {1..30}; do
  if systemctl is-active --quiet sqlguard-approval.service; then
    STATUS="$(curl --silent --output /dev/null --write-out '%{http_code}' \
       --max-time 2 -H 'Host: aprobaciones.hacheinteractive.com' \
       http://127.0.0.1:8173/root-window || true)"
    if [[ "$STATUS" == 401 ]]; then READY=1; break; fi
  fi
  sleep 0.2
done
[[ "$READY" == 1 ]] || { echo SYSTEMD_SMOKE_FAILED >&2; exit 2; }
# Run as the approval service identity, without ever disclosing tickets/secrets.
runuser -u sqlguard-approval -- python3 - <<'PY'
import json,socket
sock=socket.socket(socket.AF_UNIX)
sock.settimeout(3)
try:
    sock.connect("/run/hache-root-window/admin.sock")
    sock.sendall(b'{"method":"status"}\n')
    response=json.loads(sock.recv(4096))
finally:
    sock.close()
if not response.get("ok") or response["result"].get("enabled") is not False:
    raise SystemExit("WINDOW_SOCKET_FAILURE")
print("WINDOW_SOCKET_OK_DEFAULT_OFF")
PY

# Keep exact public allowlist. Roll back automatically if Nginx fails validation.
install -o root -g root -m 0644 "$VHOST" "$NGINX"
NGINX_CHANGED=1
nginx -t
systemctl reload nginx
# Wait for Nginx to serve the new vhost. "systemctl reload" can return
# before worker processes start using the updated configuration.
# Check both loopback via TLS SNI and the public domain (never use -k).
# An unauthenticated browser must receive 401, and SQL APIs must remain 503.
read_http_code(){
  curl --noproxy '*' --silent --show-error -o /dev/null -w '%{http_code}' \
    --connect-timeout 2 --max-time 5 "$@" 2>/dev/null || true
}
loopback_code=000; public_code=000; blocked_local=000; blocked_public=000
READY_PUBLIC=0
for attempt in {1..30}; do
  loopback_code="$(read_http_code --resolve aprobaciones.hacheinteractive.com:443:127.0.0.1 https://aprobaciones.hacheinteractive.com/root-window)"
  blocked_local="$(read_http_code --resolve aprobaciones.hacheinteractive.com:443:127.0.0.1 https://aprobaciones.hacheinteractive.com/api/agent/stage)"
  public_code="$(read_http_code https://aprobaciones.hacheinteractive.com/root-window)"
  blocked_public="$(read_http_code https://aprobaciones.hacheinteractive.com/api/agent/stage)"
  if [[ "$loopback_code" == 401 && "$blocked_local" == 503 &&
        "$public_code" == 401 && "$blocked_public" == 503 ]]; then
    READY_PUBLIC=1
    break
  fi
  sleep 0.5
done
if [[ "$READY_PUBLIC" != 1 ]]; then
  printf 'PUBLIC_AUTH_FAILURE local=%s public=%s local_sql=%s public_sql=%s\n' \
      "$loopback_code" "$public_code" "$blocked_local" "$blocked_public" >&2
  exit 2
fi
SUCCESS=1
echo "ROOT_WINDOW_WEB_READY_PASSKEY_OWNER_ACTION_REQUIRED"
echo "OWNER_PASSWORD_STORED_LOCALLY_AT: $OWNER_PASS (DO NOT SEND TO CHAT)"
