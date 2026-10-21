#!/usr/bin/env bash
# One-time root bootstrap of reviewed, merged source; leaves web authorization OFF.
set -Eeuo pipefail
if [[ "$EUID" != 0 || "$#" != 2 ]]; then
  echo "USAGE: root install.sh MERGED_SHA40 CLEAN_GIT_CHECKOUT" >&2
  exit 2
fi
SHA="$1"
SOURCE="$(realpath -- "$2")"
[[ "$SHA" =~ ^[0-9a-f]{40}$ && -d "$SOURCE/.git" ]] || exit 2
[[ "$(git -C "$SOURCE" rev-parse HEAD)" == "$SHA" ]] || { echo COMMIT_MISMATCH >&2; exit 2; }
[[ -z "$(git -C "$SOURCE" status --porcelain --untracked-files=all)" ]] || { echo DIRTY_SOURCE >&2; exit 2; }
git -C "$SOURCE" merge-base --is-ancestor "$SHA" origin/main || { echo UNMERGED_SOURCE >&2; exit 2; }
URL="$(git -C "$SOURCE" remote get-url origin)"
[[ "$URL" == https://github.com/manglefurniture/Hache-Base.git || "$URL" == https://github.com/manglefurniture/Hache-Base ]] || exit 2
SRC="$SOURCE/extensions/root-window"
for f in window.py test_window.py deploy/hache-root-window.service.example; do
  [[ -f "$SRC/$f" && ! -L "$SRC/$f" ]] || exit 2
done
getent passwd sqlguard-approval >/dev/null
getent passwd gpt-agent >/dev/null
(cd "$SRC" && python3 -m unittest -q test_window.py && python3 -m py_compile window.py)
R=/opt/hache-root-window
RELEASE="$R/releases/$SHA"
[[ ! -e "$RELEASE" && ! -L "$RELEASE" ]] || { echo RELEASE_EXISTS >&2; exit 2; }
install -d -o root -g root -m 0755 "$R" "$R/releases" "$RELEASE" "$RELEASE/deploy"
install -d -o root -g root -m 0700 /etc/hache-root-window /var/lib/hache-root-window
install -o root -g root -m 0644 "$SRC/window.py" "$RELEASE/window.py"
install -o root -g root -m 0644 "$SRC/deploy/hache-root-window.service.example" "$RELEASE/deploy/hache-root-window.service.example"
CONFIG=/etc/hache-root-window/config.json
if [[ ! -e "$CONFIG" ]]; then
  python3 - <<'PY'
import json,os,pwd
p="/etc/hache-root-window/config.json"
admin=pwd.getpwnam("sqlguard-approval")
agent=pwd.getpwnam("gpt-agent")
cfg=dict(database="/var/lib/hache-root-window/replay.sqlite",
         secret_hex=os.urandom(32).hex(),admin_uid=admin.pw_uid,
         agent_uid=agent.pw_uid,admin_gid=admin.pw_gid,agent_gid=agent.pw_gid,
         admin_socket="/run/hache-root-window/admin.sock",
         agent_socket="/run/hache-root-window/agent.sock")
fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
with os.fdopen(fd,"w") as f:
    json.dump(cfg,f,sort_keys=True)
    f.write("\n")
PY
fi
[[ -f "$CONFIG" && ! -L "$CONFIG" && "$(stat -c %u:%g:%a "$CONFIG")" == 0:0:600 ]] || { echo UNSAFE_CONFIG >&2; exit 2; }
python3 - "$RELEASE/window.py" "$CONFIG" <<'PY'
import importlib.util,sys
spec=importlib.util.spec_from_file_location("rw",sys.argv[1])
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.safe_config(sys.argv[2])
PY
PREVIOUS="$(readlink -f "$R/current" 2>/dev/null || true)"
ln -s "$RELEASE" "$R/.next-$SHA"
mv -Tf "$R/.next-$SHA" "$R/current"
install -o root -g root -m 0644 "$RELEASE/deploy/hache-root-window.service.example" /etc/systemd/system/hache-root-window.service
rollback(){
  local rc=$?
  trap - ERR
  systemctl stop hache-root-window.service >/dev/null 2>&1 || true
  if [[ -n "$PREVIOUS" && -d "$PREVIOUS" ]]; then
    ln -s "$PREVIOUS" "$R/.rollback-$SHA"
    mv -Tf "$R/.rollback-$SHA" "$R/current"
  fi
  exit "$rc"
}
trap rollback ERR
systemctl daemon-reload
systemctl enable --now hache-root-window.service
systemctl is-active --quiet hache-root-window.service
[[ -S /run/hache-root-window/admin.sock && -S /run/hache-root-window/agent.sock ]] || { echo SOCKETS_MISSING >&2; false; }
trap - ERR
echo ROOT_WINDOW_BOOTSTRAPPED_DEFAULT_OFF_SQLGUARD_WEB_UNCHANGED
