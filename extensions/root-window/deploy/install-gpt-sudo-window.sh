#!/usr/bin/env bash
# Root owner installs reviewed, immutable temporary sudo infrastructure.
# Does NOT open any root window; installation always revokes stale grant first.
set -Eeuo pipefail
[[ "$EUID" == 0 && "$#" == 2 ]] || {
  echo "USAGE: install-gpt-sudo-window.sh MERGED_SHA40 CLEAN_GIT_CHECKOUT" >&2
  exit 2
}
SHA="$1"
REPO="$(realpath -- "$2")"
[[ "$SHA" =~ ^[0-9a-f]{40}$ && -d "$REPO/.git" ]] || exit 2
[[ "$(git -C "$REPO" rev-parse HEAD)" == "$SHA" ]] || { echo COMMIT_MISMATCH >&2; exit 2; }
[[ -z "$(git -C "$REPO" status --porcelain --untracked-files=all)" ]] || { echo DIRTY_SOURCE >&2; exit 2; }
git -C "$REPO" merge-base --is-ancestor "$SHA" origin/main || { echo UNMERGED_SOURCE >&2; exit 2; }
ORIGIN="$(git -C "$REPO" remote get-url origin)"
[[ "$ORIGIN" == "https://github.com/manglefurniture/Hache-Base.git" ||
   "$ORIGIN" == "https://github.com/manglefurniture/Hache-Base" ]] || { echo INVALID_REMOTE >&2; exit 2; }
SRC="$REPO/extensions/root-window/deploy"
HELPER="$SRC/hache-gpt-sudo-window.sh"
UNIT="$SRC/hache-gpt-sudo-bootguard.service.example"
[[ -f "$HELPER" && ! -L "$HELPER" && -f "$UNIT" && ! -L "$UNIT" ]] ||
  { echo FILE_MISSING >&2; exit 2; }
bash -n "$HELPER"
bash -n "$SRC/install-gpt-sudo-window.sh"
getent passwd gpt-agent >/dev/null
test -x /usr/sbin/visudo
test -x /usr/bin/systemd-run

# Do not deploy versioned production code except from exact reviewed commit.
install -o root -g root -m 0755 "$HELPER" /usr/local/sbin/hache-gpt-sudo-window
install -o root -g root -m 0644 "$UNIT" /etc/systemd/system/hache-gpt-sudo-bootguard.service
systemctl daemon-reload
systemctl enable --now hache-gpt-sudo-bootguard.service
systemctl is-enabled --quiet hache-gpt-sudo-bootguard.service
systemctl is-active --quiet hache-gpt-sudo-bootguard.service
/usr/local/sbin/hache-gpt-sudo-window status
echo GPT_TEMPORARY_SUDO_HELPER_READY_OFF
echo 'ACTIVATE: /usr/local/sbin/hache-gpt-sudo-window start 10'
echo 'REVOKE:   /usr/local/sbin/hache-gpt-sudo-window stop'
