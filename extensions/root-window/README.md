# Root window for Hache - safe foundations

Status: GitHub proposal, not active in production. This is NOT a generic root access toggle and intentionally does not install sudo access, a root shell, or arbitrary command execution.

A narrowly scoped root broker receives owner-approved, 30-second, HMAC-signed tickets over a private admin Unix socket. It accepts exactly two actions: enable for 600 seconds or disable immediately. Only the approval service UID may use that socket. The broker separately checks gpt-agent Linux credentials over another Unix socket, and only allows status or restart_operator. Three attempts maximum per window, at least 60 seconds apart. Restart is rejected if the independent Vast financial guardian cannot be verified or any financial lease is armed.

Authorization lives in volatile memory, so a daemon restart closes the window. Signature is bound to a domain, scope, action, duration and random one-use nonce. Replay prevention and audit are stored in a root-only SQLite database. Grant expiry uses a monotonic clock. No credentials, shell commands, paths, service names or parameters can be injected by the agent.

The HMAC ticket MUST originate from a verified WebAuthn owner ceremony on the existing SQLGuard approval origin. NEVER interpret an unverified ChatGPT answer or the no-grant passkey check as approval. No function should be advertised as operational until this authenticated issuer, protected HTTPS UI, socket groups and root bootstrap have been independently installed, tested, and reviewed.

Root bootstrap requirements: install this exact merged release under /opt/hache-root-window/current owned by root and immutable to the agent; configure /etc/hache-root-window/config.json root:root 0600, with 32-byte shared secret and verified UID/GID for the approval service and gpt-agent; create /run/hache-root-window owned root 0755 and /var/lib/hache-root-window root 0700. Keep the admin socket inaccessible to the agent. Install an audited systemd service with strict filesystem hardening, review live financial guard behavior and verify audit/replay persistence. NEVER share the secret through chat, GitHub, or web. Lock down nginx to specific paths and preserve the current 503 until owner passkey flow is production-ready.

Only one allowed mutation: restart hache-mining-operator.service if the cost cutoff guardian is healthy. For deployments, GitHub CI and the existing one-use deployment gate remain mandatory. Rental of Vast GPUs and all database changes remain outside this feature.

Tests: python3 -m unittest discover -s extensions/root-window -p 'test_*.py' -v

## Atomicity of Vast lease exclusion
The restart takes `BEGIN IMMEDIATE` on the exact operator SQLite database and holds it until `systemctl restart` and `is-active` finish. The miner's `arm()` and `arm_rental()` use `BEGIN IMMEDIATE` on that same file, so they cannot commit a new armed lease between the check and the restart. A concurrent lease causes timeout/fail-closed, not a forced restart. The root-window unit needs a narrowly reviewed `ReadWritePaths=/var/lib/hache-mining-operator` to acquire SQLite writer reservation, but does not modify lease rows (transaction rolled back). Security review must verify existing SQLite journaling and filesystem ownership and reject if isolation cannot be guaranteed.
