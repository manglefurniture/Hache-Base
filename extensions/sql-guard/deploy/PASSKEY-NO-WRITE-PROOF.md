# SQL Guard — no-write proof of registered passkey

Only authenticates the registered WebAuthn credential. It does not stage SQL writes,
create approval grants, enable MariaDB permissions, or start the SQL runner.

## Safety and deployment gates
1. Merge only after SQL Guard tests, Hache-Base CI and automated review.
2. Build a new immutable root-owned release from exact GitHub blobs. Do not edit the installed release directly.
3. Keep a rollback symlink to the previous release and leave public Nginx at 503.
4. Start only the approval service on 127.0.0.1:8173 and check one-worker memory constraints.
5. Verify local GET /verify-passkey returns 200, while agent/approval routes stay unauthorized.
6. Use the versioned passkey-check-only Nginx vhost to publish only exact paths:
   GET /verify-passkey, /static/passkey_check.js and /static/approval.css;
   POST /api/passkey-check/start and /api/passkey-check/finish.
7. All API paths for staging, approval, enrollment, status and SQL remain HTTP 503.
8. Require valid HTTPS, DNS-only direct A/AAAA origin, root-owned config backup and nginx -t.
9. Owner verifies from Chrome Android. Expected UI: Passkey verificada. No se autorizó ninguna operación.
10. Immediately restore the HTTP 503 vhost, stop the approval service and verify passkeys=1,
    no new approvals, no new SQL requests, using only aggregate counts from root.

## Security characteristics
- Signed, one-use WebAuthn challenge bound to exact HTTPS RP ID and origin, requiring user verification.
- Challenge expires after 120 seconds, maximum three active and six starts per UTC hour.
- Persistent private SQLite stores only challenge, quota and passkey sign counter; no approval is issued.
- No old bootstrap activation token is required for this passkey authentication self-check.
- The public allowlist must never be deployed behind a proxy without reviewed real-IP policy.
- After closure, no HTTP passkey routes are public and runner remains off.
- This does not authorize SQL mutation, root brokerage or MariaDB privilege cutover.
