#!/usr/bin/env bash
# Root-only bootstrap, after owner reviews the merged GitHub commit and package digest.
# Never deploys HACHE-MINER or modifies an existing mining operator on bootstrap.
set -Eeuo pipefail
if [[ "$(id -u)" != 0 ]]; then echo "ROOT_REQUIRED" >&2; exit 2; fi
if [[ "$#" != 3 ]]; then
  echo "Usage: install.sh <merged-commit-40hex> <root-reviewed-bundle.tar.gz> <expected-sha256>" >&2
  exit 2
fi
COMMIT="$1"; INBOX="$2"; EXPECTED="$3"
[[ "$COMMIT" =~ ^[0-9a-f]{40}$ && "$EXPECTED" =~ ^[0-9a-f]{64}$ ]] || exit 2
[[ "$INBOX" == /* && -f "$INBOX" && ! -L "$INBOX" ]] || exit 2
R=/opt/hache-deploy-gate
DEST="$R/releases/$COMMIT"
test ! -e "$DEST" && test ! -L "$DEST"
TEMP="$(mktemp -d /root/hache-deploy-install.XXXXXXXX)"
trap 'rm -rf -- "$TEMP"' EXIT
cp -- "$INBOX" "$TEMP/deploy.tar.gz"
[[ "$(sha256sum "$TEMP/deploy.tar.gz" | cut -d' ' -f1)" == "$EXPECTED" ]] || {
 echo "BUNDLE_DIGEST_MISMATCH" >&2; exit 2;
}
mkdir -m 0700 "$TEMP/source"
python3 - "$TEMP/deploy.tar.gz" "$TEMP/source" <<'PY'
import pathlib,sys,tarfile
src=pathlib.Path(sys.argv[1]); dest=pathlib.Path(sys.argv[2])
allowed={'deploy_gate.py','authorize.py','client.py','test_deploy_gate.py',
'deploy/hache-deploy-gate.service.example','deploy/hache-deploy-gate.socket.example'}
with tarfile.open(src,'r:gz') as tar:
    members=tar.getmembers()
    assert {m.name for m in members}==allowed and len(members)==len(allowed)
    assert all(m.isfile() and 0<m.size<300000 for m in members)
    for item in members:
        target=dest/item.name
        target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        with open(target,'xb') as out:
            out.write(tar.extractfile(item).read())
PY
(
 cd "$TEMP/source"
 python3 -m py_compile deploy_gate.py authorize.py client.py test_deploy_gate.py
 python3 -m unittest -q test_deploy_gate
)
install -d -o root -g root -m 0755 "$R" "$R/releases"
install -d -o root -g root -m 0700 /etc/hache-deploy-gate
install -d -o root -g root -m 0700 /var/lib/hache-deploy-gate
install -d -o root -g root -m 0700 /var/lib/hache-deploy-gate/grants
install -d -o root -g root -m 0700 /var/lib/hache-deploy-gate/approved-sources
install -d -o root -g root -m 0755 /var/spool/hache-deploy-inbox
install -d -o gpt-agent -g gpt-agent -m 0700 /var/spool/hache-deploy-inbox/hache-miner
install -d -o gpt-agent -g gpt-agent -m 0700 /var/spool/hache-deploy-inbox/hache-base
if [[ ! -e /etc/hache-deploy-gate/config.json ]]; then
 python3 - <<'PY'
import json,os
p='/etc/hache-deploy-gate/config.json'
f=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
try:
 with os.fdopen(f,'w') as out:
  json.dump({'agent_uid':__import__('pwd').getpwnam('gpt-agent').pw_uid,
   'database':'/var/lib/hache-deploy-gate/plans.sqlite',
   'state_dir':'/var/lib/hache-deploy-gate',
   'grants':'/var/lib/hache-deploy-gate/grants',
   'inbox':'/var/spool/hache-deploy-inbox'},out,sort_keys=True)
  out.write('\n')
except:raise
PY
fi
cp -a "$TEMP/source" "$DEST"
find "$DEST" -type d -exec chmod 0755 '{}' +
find "$DEST" -type f -exec chmod 0644 '{}' +
install -o root -g root -m 0644 "$DEST/deploy/hache-deploy-gate.service.example" /etc/systemd/system/hache-deploy-gate.service
install -o root -g root -m 0644 "$DEST/deploy/hache-deploy-gate.socket.example" /etc/systemd/system/hache-deploy-gate.socket
OLD="$(readlink -f "$R/current" 2>/dev/null || true)"
CANDIDATE="$R/.next-$COMMIT"
ln -s "$DEST" "$CANDIDATE"
mv -Tf "$CANDIDATE" "$R/current"
restore(){
 local status=$?
 trap - ERR
 if [[ -n "$OLD" && -d "$OLD" ]]; then
  ln -s "$OLD" "$R/.rollback-$COMMIT"
  mv -Tf "$R/.rollback-$COMMIT" "$R/current"
  systemctl restart hache-deploy-gate.service || true
 else
  systemctl disable --now hache-deploy-gate.service hache-deploy-gate.socket || true
 fi
 exit "$status"
}
trap restore ERR
systemctl daemon-reload
systemctl enable --now hache-deploy-gate.socket
systemctl enable --now hache-deploy-gate.service
systemctl is-active --quiet hache-deploy-gate.socket
systemctl is-active --quiet hache-deploy-gate.service
runuser -u gpt-agent -- python3 "$R/current/client.py" '{"method":"capabilities"}' |
 python3 -c 'import json,sys;r=json.load(sys.stdin);assert r["ok"];print("DEPLOY_GATE_PASS")'
trap - ERR
echo "DEPLOY_GATE_BOOTSTRAP_OK_NO_PRODUCT_RELEASE_ACTIVATED"
