# SQL Guard: local-only approval smoke test (1 GiB VPS)

The isolated approval service is configured with a single Gunicorn worker,
loopback binding `127.0.0.1:8173`, `MemoryHigh=160M`, and
`MemoryMax=224M` because MariaDB, Nginx, and other application services
share a 1 GiB machine. This is an initial resource cap, not an availability
guarantee. Observe RSS, OOM counters and journald before extending exposure.

After the exact GitHub commit has passed CI and is merged, the owner installs
the versioned unit as root. The existing systemd unit is root-owned, and only
the unit file is replaced (with a backup kept under `/root` for rollback).
Reload systemd, but **do not enable** the new unit or modify Nginx.

For the first smoke test, the owner may run `systemctl start
sqlguard-approval.service` while the public HTTPS site still returns
503. Check `systemctl status`, journald, loopback-only listener, denial of
anonymous mutation, and the ability to serve `/enroll` locally with a correct
Host header. Stop the unit on failure. Never paste environment file contents,
tokens, cookies, or challenges in ChatGPT.

Public enrollment is a **separate later gate**, after browser security,
rate limiting, and HTTPS reverse-proxy behavior are reviewed. The human must
enter the one-time enrollment token from the root console directly into the
site on Android; it must never be copied into chats or connector output.

A registered passkey does not authorize SQL Guard to revoke current MariaDB
grants or to expose the root administrative broker. Those gates require their
own tests and explicit owner confirmation.
