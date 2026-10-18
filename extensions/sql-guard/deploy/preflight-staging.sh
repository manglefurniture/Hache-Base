#!/usr/bin/env bash
# SQL Guard staging diagnostic. READ-ONLY: never install, grant, start or reload.
set -Eeuo pipefail

usage() {
  cat <<'EOF'
Usage: bash extensions/sql-guard/deploy/preflight-staging.sh [--report|--require-staged]
--report          Show current state without changing anything (default).
--require-staged  Exit 1 if isolated identities, groups, paths or unit files
                  are not prepared. Does NOT validate WebAuthn or DB cutover.
EOF
}
mode="${1:---report}"
if [[ "$mode" == "--help" || "$mode" == "-h" ]]; then usage; exit 0; fi
if [[ "$mode" != "--report" && "$mode" != "--require-staged" || $# -gt 1 ]]; then
  usage >&2
  exit 2
fi

missing=0
check() {
  local what="$1" result="$2"
  printf '%-34s %s\n' "$what" "$result"
  if [[ "$result" != "OK" ]]; then missing=$((missing + 1)); fi
}
user_exists() { getent passwd "$1" >/dev/null 2>&1; }
group_exists() { getent group "$1" >/dev/null 2>&1; }
group_includes() {
  local groups
  groups="$(id -nG "$1" 2>/dev/null)" || return 1
  [[ " $groups " == *" $2 "* ]]
}
group_excludes() {
  id -nG "$1" >/dev/null 2>&1 || return 1
  ! group_includes "$1" "$2"
}
unit_exists() { systemctl cat "$1" >/dev/null 2>&1; }
dir_owned() {
  local path="$1" spec="$2" actual
  [[ -d "$path" && ! -L "$path" ]] || return 1
  actual="$(stat -c '%U:%G:%a' "$path" 2>/dev/null)" || return 1
  [[ "$actual" == "$spec" ]]
}
file_immutable() {
  local path="$1" owner="$2" perms
  [[ -f "$path" && ! -L "$path" ]] || return 1
  perms="$(stat -c '%U:%a' "$path" 2>/dev/null)" || return 1
  [[ "$perms" == "$owner" ]]
}

printf '%s\n' 'SQL Guard staging inspection — diagnostic only (no changes)'
check "GPT user" "$(user_exists gpt-agent && echo OK || echo MISSING)"
check "Approval user" "$(user_exists sqlguard-approval && echo OK || echo MISSING)"
check "Runner user" "$(user_exists sqlguard-runner && echo OK || echo MISSING)"
check "Shared store group" "$(group_exists sqlguard-store && echo OK || echo MISSING)"
check "Agent socket group" "$(group_exists sqlguard-callers && echo OK || echo MISSING)"
check "Approval in store group" "$(group_includes sqlguard-approval sqlguard-store && echo OK || echo MISSING)"
check "Runner in store group" "$(group_includes sqlguard-runner sqlguard-store && echo OK || echo MISSING)"
check "Runner in socket group" "$(group_includes sqlguard-runner sqlguard-callers && echo OK || echo MISSING)"
check "GPT in socket group" "$(group_includes gpt-agent sqlguard-callers && echo OK || echo MISSING)"
check "GPT excluded from store" "$(group_excludes gpt-agent sqlguard-store && echo OK || echo MISSING)"
check "Approver excluded from socket" "$(group_excludes sqlguard-approval sqlguard-callers && echo OK || echo MISSING)"
check "Store directory root/group" "$(dir_owned /var/lib/sqlguard 'root:sqlguard-store:2770' && echo OK || echo MISSING)"
check "Trusted backup root/group" "$(dir_owned /var/lib/sqlguard-trusted 'root:sqlguard-store:750' && echo OK || echo MISSING)"
check "Runner socket directory" "$(dir_owned /run/sqlguard 'root:sqlguard-runner:771' && echo OK || echo MISSING)"
check "Approval code release" "$([[ -f /opt/sqlguard/current/extensions/sql-guard/approval_web.py ]] && echo OK || echo MISSING)"
check "Approval unit installed" "$(unit_exists sqlguard-approval.service && echo OK || echo MISSING)"
check "Runner unit installed" "$(unit_exists sqlguard-runner.service && echo OK || echo MISSING)"

for name in mariadb.service nginx.service desktop-commander-gpt.service; do
  check "Existing ${name}" "$(systemctl is-active --quiet "$name" && echo OK || echo INACTIVE)"
done

http_result="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}/%{ssl_verify_result}' --max-time 8 https://aprobaciones.hacheinteractive.com/ 2>/dev/null || true)"
printf '%-34s %s\n' "HTTPS approval (informational)" "${http_result:-UNAVAILABLE}"
printf '%s\n' 'NOT CHECKED: root-only secret files, actual SQL grants, trusted backup restore, WebAuthn ownership, network exposure.'
printf '%s\n' 'Do not enable endpoints or revoke DB permissions based on this report alone.'
if [[ "$mode" == "--require-staged" && "$missing" -ne 0 ]]; then
  printf 'STAGING_NOT_READY: %d missing/inactive checks\n' "$missing"
  exit 1
fi
printf 'DIAGNOSTIC_COMPLETE: %d missing/inactive checks\n' "$missing"
