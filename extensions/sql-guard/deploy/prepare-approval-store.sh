#!/usr/bin/env bash
# Owner-operated SQL Guard preflight and isolated SQLite bootstrap.
# No secret values printed. No systemd start, Nginx or MariaDB changes.
set -Eeuo pipefail
mode="--check"
if [[ $# -gt 0 ]]; then mode="$1"; fi
if [[ $# -gt 1 || "$mode" != "--check" && "$mode" != "--init-store" ]]; then
  echo "Usage: bash prepare-approval-store.sh --check|--init-store" >&2
  exit 2
fi
die() { printf 'REFUSED: %s\n' "$*" >&2; exit 1; }
[[ "$(id -u)" == 0 ]] || die "Root session required even for secret metadata check"
for cmd in stat getent id runuser systemctl; do
  command -v "$cmd" >/dev/null || die "Missing tool: $cmd"
done

owner_mode() {
  local path="$1" expected="$2" actual
  [[ -f "$path" && ! -L "$path" && -s "$path" ]] ||
    die "Missing, empty or symlinked protected file: $path"
  actual="$(stat -c '%u:%g:%a' "$path")"
  [[ "$actual" == "$expected" ]] ||
    die "Unexpected owner/mode for $path (no changes made)"
}
directory_mode() {
  local path="$1" expected="$2" actual
  [[ -d "$path" && ! -L "$path" ]] || die "Missing or symlinked directory: $path"
  actual="$(stat -c '%u:%g:%a' "$path")"
  [[ "$actual" == "$expected" ]] || die "Unexpected owner/mode for $path"
}

owner_mode /etc/sqlguard/approval.env "0:0:600"
owner_mode /root/sqlguard-enrollment-token "0:0:600"
directory_mode /etc/sqlguard "0:0:700"
directory_mode /root "0:0:700"
directory_mode /var/lib/sqlguard "0:$(getent group sqlguard-store | cut -d: -f3):2770"
[[ "$(id -gn sqlguard-approval)" == sqlguard-store ]] ||
  die "Approval user does not have private store primary group"
id -nG sqlguard-runner | tr ' ' '\n' | grep -qx sqlguard-store ||
  die "Runner missing private store group"
if id -nG gpt-agent | tr ' ' '\n' | grep -qx sqlguard-store; then
  die "Untrusted agent can access private store"
fi
for unit in sqlguard-approval.service sqlguard-runner.service; do
  [[ "$(systemctl is-active "$unit" 2>/dev/null || true)" != "active" ]] ||
    die "Service unexpectedly active: $unit"
  [[ "$(systemctl is-enabled "$unit" 2>/dev/null || true)" == "disabled" ]] ||
    die "Service should remain disabled: $unit"
done
CODE=/opt/sqlguard/current/extensions/sql-guard
VENV=/opt/sqlguard/venv/bin/python
[[ -f "$CODE/passkey_gateway.py" && -r "$CODE/passkey_gateway.py" ]] ||
  die "No installed versioned gateway code"
[[ -x "$VENV" ]] || die "Python venv not installed"
db=/var/lib/sqlguard/approvals.sqlite
if [[ -e "$db" || -L "$db" ]]; then
  owner_mode "$db" "$(id -u sqlguard-approval):$(getent group sqlguard-store | cut -d: -f3):660"
  dbstatus="EXISTING"
else
  dbstatus="ABSENT"
fi
printf 'SECRET_METADATA_OK: files root-only, no values displayed\n'
printf 'STORE_%s; mode=%s\n' "$dbstatus" "$mode"
if [[ "$mode" == "--check" ]]; then
  echo "CHECK_ONLY: no changes made"
  exit 0
fi

# Schema creation uses the versioned gateway as the isolated approval identity.
# The temporary placeholders below are never persisted; runtime secrets are
# read only by systemd on actual service start.
if [[ "$dbstatus" == "ABSENT" ]]; then
  # SQLite needs group-readable/writable files for the independent runner.
  umask 0007
  runuser -u sqlguard-approval -g sqlguard-store -- \
    env PYTHONPATH="$CODE" "$VENV" -c '
from passkey_gateway import PasskeyGateway
gateway = PasskeyGateway(
    "/var/lib/sqlguard/approvals.sqlite",
    rp_id="aprobaciones.hacheinteractive.com",
    origin="https://aprobaciones.hacheinteractive.com",
    owner_id="schema-initialization-only",
    signing_key=b"\0"*32,
    bootstrap_hash="0"*64)
gateway.close()
'
fi
owner_mode "$db" "$(id -u sqlguard-approval):$(getent group sqlguard-store | cut -d: -f3):660"

# Validate actual runner access, without writing or issuing approvals.
runuser -u sqlguard-runner -g sqlguard-runner -- \
  "$VENV" -c '
import sqlite3
db = sqlite3.connect("file:/var/lib/sqlguard/approvals.sqlite?mode=ro", uri=True)
tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='\''table'\''")}
required = {"passkeys", "requests", "ceremonies", "approvals", "stage_budget"}
assert required.issubset(tables), "Incomplete schema"
db.close()
'
# A fresh GPT Linux process must not be allowed to open or traverse this store.
if runuser -u gpt-agent -- "$VENV" -c '
import sqlite3
db = sqlite3.connect("file:/var/lib/sqlguard/approvals.sqlite?mode=ro", uri=True)
db.execute("SELECT name FROM sqlite_master LIMIT 1").fetchone()
' >/dev/null 2>&1; then
  die "Agent unexpectedly opened private approval store"
fi
echo "SQLGUARD_STORE_READY: schema initialized; isolated runner read allowed; agent denied"
echo "NOT STARTED: services, backups, Nginx, passkeys or MariaDB permissions"
