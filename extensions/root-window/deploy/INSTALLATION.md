# One-time root handoff (not yet a public web switch)

Review and merge this PR with green CI first. Use a trusted root shell to clone
Hache-Base, check out the exact merged SHA shown on GitHub main and invoke
the versioned installer on a clean clone:

    git clone https://github.com/manglefurniture/Hache-Base.git /root/hache-base-verified
    git -C /root/hache-base-verified checkout --detach MERGED_SHA40
    bash /root/hache-base-verified/extensions/root-window/deploy/install.sh MERGED_SHA40 /root/hache-base-verified

The installer demands root only during bootstrap. It validates clean checkout,
main ancestry, the remote, and tests before installing immutable root-owned
code and a disabled-by-default capability window. This does not grant sudo to
gpt-agent. It creates a random 32-byte signing key in root-only config, never
prints secrets, and installs only the scoped root service.

The SQLGuard approval web and Nginx 503 stay unchanged. Before enabling the
browser control, a separate audited deployment must update SQLGuard code,
configure the independent owner Basic authentication hash and a root-only
copy of the broker signing key, verify the passkey, and expose exact Nginx
routes with rate limits. Do not copy any secrets into the chat or GitHub.

Emergency revocation from a trusted root session:
    systemctl disable --now hache-root-window.service

Check:
    systemctl is-active hache-root-window.service

No existing mining service, financial watchdog or MariaDB grants are modified.
