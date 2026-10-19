# Protected deployment gate — GPT Agent without broad root rights

This component handles **GitHub code deployment**, not mining operations.
It is a separate root-only systemd service. `gpt-agent` can use only the
local peer-authenticated Unix socket; the mining broker retains its
`hache-miner` privileges. This feature does not enable general sudo, shell,
SSH, rental, GPU start, wallet edits, GitHub write access or SQL writes.

## Fixed scope

| Target | Repository | Production current |
|---|---|---|
| `hache-miner` | `manglefurniture/HACHE-MINER` | `/srv/hache-miner/current` |
| `hache-base` | `manglefurniture/Hache-Base` | `/opt/hache-mining-operator/current` |

Nothing else is accepted. The operation accepts only a **40-character commit
SHA** and **64-character archive SHA-256**; no arbitrary commands, directory
paths, service names or additional environment variables.

## Trust and security boundary

**Critical:** a SHA-256 alone is *not proof* that the source matches a GitHub
commit. Before the root approval, the owner/trusted administrative approver
must independently verify (1) the exact SHA is merged to `main`, (2) the
GitHub Actions runs for that SHA are green, and (3) the submitted tar.gz
is actually derived from that commit and has the approved SHA-256. The
`--owner-verified-ci` switch is an **attestation by that separate trusted
approver**, not an automated GitHub API check; it must not be supplied based
only on the agent's claims.

An agent may prepare a candidate tar in the following upload-only directories
created by the bootstrap script:

```
/var/spool/hache-deploy-inbox/hache-miner/<commit>.tar.gz
/var/spool/hache-deploy-inbox/hache-base/<commit>.tar.gz
```

The gate copies from the agent-owned path into a private root-controlled
cache, closes TOCTOU by checking SHA-256 on the copy, validates every tar
member and rejects traversal, symlinks/hardlinks, special nodes, oversized
bundles and credential-like names. It pins the content in the plan snapshot
with the currently active release. Once owner-approved, the broker atomically
changes the database phase to `claimed` **before any production change**.
Unknown outcomes burn authorization and require operator reconciliation.

Deployment phases: copy validated archive, extract into a private staging
directory, check anchors + PHP/Python syntax, atomically publish immutable
release, atomically switch the `current` symlink, check fixed service health,
and roll back the link if a health check fails. The old release remains.
The gate does not restart HACHE-MINER, Vast or Salad. For `hache-base`
it restarts **only** `hache-mining-operator.service`, preserving the
independent financial lease timer and active stop obligations.

The initial bootstrap is **not performed by gpt-agent**; its service source
and archive SHA must be verified and installed by root using
`deploy/install.sh`. This is a one-time privileged infrastructure step.

## Commands — client after bootstrap

```bash
python3 /opt/hache-deploy-gate/current/client.py '{"method":"capabilities"}'

# Prepare, no production change (source tar already in the inbox):
python3 /opt/hache-deploy-gate/current/client.py \
  '{"method":"prepare","target":"hache-miner","commit":"<40hex>","archive_sha256":"<64hex>"}'
```

`prepare` returns `plan_id`, `digest`, `snapshot`, `expires_at`.
A root operator independently verifies the commit, CI and actual archive, and
explicitly authorizes that exact plan (requires matching values):

```bash
python3 /opt/hache-deploy-gate/current/authorize.py \
 --plan-id <32hex> --expected-digest <64hex> --target hache-miner \
 --commit <40hex> --archive-sha256 <64hex> --owner-verified-ci
```

Once granted, GPT Agent can submit:

```bash
python3 /opt/hache-deploy-gate/current/client.py \
 '{"method":"execute","plan_id":"<32hex>"}'
python3 /opt/hache-deploy-gate/current/client.py \
 '{"method":"status","plan_id":"<32hex>"}'
```

**Approval is not yet fully in-ChatGPT.** The root grant above still needs
a trusted administrative execution; a future verified passkey/SQLGuard
handoff can supply that without ConnectBot, but that integration is not
implemented or authorized by this PR. A reply such as "sí, hazlo" must not
be treated by the nonprivileged agent as permission to mint the root file.
This PR does not modify SQLGuard.

## Bootstrap

After the new PR is merged, package exactly these six reviewed files from
the GitHub merge commit (no untracked files) into a tar.gz:

- `deploy_gate.py`
- `authorize.py`
- `client.py`
- `test_deploy_gate.py`
- `deploy/hache-deploy-gate.socket.example`
- `deploy/hache-deploy-gate.service.example`

Use those exact names at the archive root. Stage the package in a private
location readable by root. The administrator confirms the exact SHA-256,
then runs, as root:

```bash
bash install.sh MERGED_COMMIT40 /absolute/path/reviewed-gate.tar.gz BUNDLE_SHA256
```

The bootstrap tests the package before installing or enabling the dedicated
root service. It does **not** activate either production application's
release. Its final expected output is
`DEPLOY_GATE_BOOTSTRAP_OK_NO_PRODUCT_RELEASE_ACTIVATED`.

Stop if any check fails; do not hand broad sudo access to `gpt-agent` as
a workaround. Revocation: `systemctl disable --now hache-deploy-gate.socket`
by the administrator. Historical root grants cannot be reused.

## Operational limitations

- No automated privileged approval/passkey integration yet.
- GitHub merge/CI/archive provenance is independently checked by the approver,
  not programmatically verified by this service.
- Deployment health checks are syntax/targeted service checks, not full
  end-to-end browser, API, or GPU production verification.
- Private existing credentials remain in their current locations; archives
  must not bundle secrets. No arbitrary executable maintenance hooks run.
- Archive extraction limits are conservative; certain repositories or
  packaged trees may need an explicitly reviewed update to those limits.
- A missing timer, unresolved prior stop lease, broken operator restart or
  insufficient evidence means **do not activate**.
