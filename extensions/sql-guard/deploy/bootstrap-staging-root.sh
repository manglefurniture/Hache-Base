#!/usr/bin/env bash
# Prepares isolated service identities, not root access for GPT.
set -Eeuo pipefail
umask 077
mode="--check"
if [[ $# -gt 0 ]]; then mode="$1"; fi
if [[ $# -gt 1 || "$mode" != "--check" && "$mode" != "--apply" ]]; then
  echo "Usage: bash bootstrap-staging-root.sh --check|--apply" >&2
  exit 2
fi
die() { echo "ERROR: $*" >&2; exit 1; }
script_dir="$(cd "$(dirname "$0")" && pwd -P)"
template="$script_dir/sqlguard-tmpfiles.conf.example"
target="/etc/tmpfiles.d/sqlguard.conf"
getent passwd gpt-agent >/dev/null || die "Existing gpt-agent required"
[[ "$(id -u gpt-agent)" != 0 ]] || die "gpt-agent must not be root"
[[ -f "$template" && ! -L "$template" ]] || die "Missing versioned template"
[[ "$(cat "$template")" == 'd /run/sqlguard 0771 root sqlguard-runner -' ]] ||
  die "Unexpected tmpfiles template"
member() { id -nG "$1" | tr ' ' '\n' | grep -qx "$2"; }
if getent group sqlguard-store >/dev/null && member gpt-agent sqlguard-store; then
  die "Unsafe GPT membership in private approval group"
fi
if [[ "$mode" == "--check" ]]; then
  for name in sqlguard-store sqlguard-callers sqlguard-runner; do
    getent group "$name" >/dev/null && echo "GROUP $name EXISTING" || echo "GROUP $name MISSING"
  done
  for name in sqlguard-approval sqlguard-runner; do
    getent passwd "$name" >/dev/null && echo "USER $name EXISTING" || echo "USER $name MISSING"
  done
  echo "READ_ONLY_OK (no changes)"
  exit 0
fi
[[ "$(id -u)" == 0 ]] || die "Apply requires a root session"
for util in groupadd useradd usermod install stat systemd-tmpfiles cmp awk; do
  command -v "$util" >/dev/null || die "Missing $util"
done
ensure_group() {
  getent group "$1" >/dev/null || groupadd --system "$1"
}
ensure_group sqlguard-store
ensure_group sqlguard-callers
if ! getent passwd sqlguard-approval >/dev/null; then
  useradd --system --no-create-home --home-dir /nonexistent \
    --shell /usr/sbin/nologin --gid sqlguard-store sqlguard-approval
fi
if ! getent passwd sqlguard-runner >/dev/null; then
  if getent group sqlguard-runner >/dev/null; then
    die "Runner group already exists without user: inspect manually"
  fi
  useradd --system --user-group --no-create-home --home-dir /nonexistent \
    --shell /usr/sbin/nologin \
    --groups sqlguard-store,sqlguard-callers sqlguard-runner
fi
account_check() {
  local user="$1" primary="$2" supplemental="$3" group
  [[ "$(getent passwd "$user" | cut -d: -f7)" == /usr/sbin/nologin ]] ||
    die "Unexpected login shell for $user"
  [[ "$(id -gn "$user")" == "$primary" ]] || die "Wrong group for $user"
  for group in $supplemental; do
    member "$user" "$group" || die "$user missing $group"
  done
}
account_check sqlguard-approval sqlguard-store sqlguard-store
account_check sqlguard-runner sqlguard-runner "sqlguard-store sqlguard-callers"

# Never accept an existing account with root's UID, the agent's UID or any
# alias UID. A shared UID defeats filesystem and systemd user isolation.
unique_unprivileged_uid() {
  local user="$1" uid names
  uid="$(id -u "$user")"
  [[ "$uid" =~ ^[0-9]+$ && "$uid" -gt 0 ]] ||
    die "$user has privileged or invalid UID"
  names="$(getent passwd | awk -F: -v wanted="$uid" '$3 == wanted {print $1}')"
  [[ "$names" == "$user" ]] || die "$user has a reused UID"
}
unique_unprivileged_uid gpt-agent
unique_unprivileged_uid sqlguard-approval
unique_unprivileged_uid sqlguard-runner

# Inspect both explicit group lists and primary-GID accounts before creating
# any group-writable secret store. Reject all unexpected service memberships.
verify_private_group() {
  local group="$1" allowed="$2" details gid explicit user pw uid primary rest
  details="$(getent group "$group")" || die "Missing private group: $group"
  gid="$(printf '%s\n' "$details" | cut -d: -f3)"
  explicit="$(printf '%s\n' "$details" | cut -d: -f4)"
  local -a group_members=()
  IFS=',' read -r -a group_members <<< "$explicit"
  for user in "${group_members[@]}"; do
    [[ -z "$user" ]] && continue
    [[ " $allowed " == *" $user "* ]] ||
      die "Unexpected explicit member $user in $group"
  done
  while IFS=: read -r user pw uid primary rest; do
    if [[ "$primary" == "$gid" && " $allowed " != *" $user "* ]]; then
      die "Unexpected primary-GID member $user in $group"
    fi
  done < <(getent passwd)
}
verify_private_group sqlguard-store "sqlguard-approval sqlguard-runner"
verify_private_group sqlguard-callers "gpt-agent sqlguard-runner"

ensure_directory() {
  local path="$1" owner="$2" group="$3" mode="$4" current
  [[ ! -L "$path" ]] || die "Symlink forbidden: $path"
  if [[ -e "$path" ]]; then
    [[ -d "$path" ]] || die "Unexpected non-directory: $path"
    current="$(stat -c '%U:%G:%a' "$path")"
    [[ "$current" == "$owner:$group:$mode" ]] ||
      die "Unexpected existing directory: $path $current"
  else
    install -d -o "$owner" -g "$group" -m "$mode" "$path"
  fi
}
ensure_directory /etc/sqlguard root root 700
ensure_directory /opt/sqlguard root root 755
ensure_directory /var/lib/sqlguard root sqlguard-store 2770
ensure_directory /var/lib/sqlguard-trusted root sqlguard-store 750
if [[ -e "$target" || -L "$target" ]]; then
  [[ -f "$target" && ! -L "$target" ]] || die "Unexpected tmpfiles target"
  [[ "$(stat -c '%U:%G:%a' "$target")" == root:root:644 ]] ||
    die "Unexpected tmpfiles ownership"
  cmp -s "$template" "$target" || die "Tmpfiles already differs from versioned file"
else
  install -o root -g root -m 0644 "$template" "$target"
fi
systemd-tmpfiles --create "$target"
[[ "$(stat -c '%U:%G:%a' /run/sqlguard)" == root:sqlguard-runner:771 ]] ||
  die "Runner socket path not securely provisioned"
if ! member gpt-agent sqlguard-callers; then
  usermod -a -G sqlguard-callers gpt-agent
fi
if member gpt-agent sqlguard-store; then
  die "Unsafe private store group detected"
fi
echo "STAGING_BOOTSTRAP_OK — identities, groups and directories only"
echo "No sudo grants, SQL privileges, secrets, services or public endpoints changed"
echo "Restart of existing GPT service is deferred until planned verification"
