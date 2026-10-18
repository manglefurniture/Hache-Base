"""Privileged-runner library: approval consumption before bounded MariaDB writes.

No HTTP endpoint here. The runner must live in a separate Linux account and
must not expose its signing key, DB credentials, or SQLite store to gpt-agent.
"""
import json
import time
from dataclasses import dataclass

from approval import Approval, canonical_operation
from mariadb_executor import Change, UnsafeMutation, apply


class ApprovalRequired(PermissionError):
    pass


@dataclass(frozen=True)
class RunnerConfig:
    schema: dict
    primary_keys: dict
    small_limit: int = 10
    absolute_limit: int = 1000


def execute_guarded(conn, approval_store, operation: dict, *, config: RunnerConfig,
                    nonce: str | None = None, verifier_key: bytes | None = None,
                    backup_checker=None, now: int | None = None) -> int:
    """Execute one small scoped mutation, or a larger approved exact-count one.

    For mass writes, SQLite approval is consumed *before* attempting MariaDB
    changes; a failure burns the approval and needs human reconciliation.
    The server operator MUST protect both databases and the runtime.
    """
    canonical_operation(operation)
    if not isinstance(config.small_limit, int) or not 1 <= config.small_limit < config.absolute_limit <= 1000:
        raise ValueError("Invalid runner limits")
    if operation["operation"] not in {"update", "delete"}:
        raise UnsafeMutation("Runner only handles UPDATE/DELETE")
    if not isinstance(operation["where"], dict) or not operation["where"]:
        raise UnsafeMutation("Scope is required")
    if not isinstance(operation["values"], dict):
        raise UnsafeMutation("Invalid values")
    change = Change(
        operation["database"], operation["table"],
        operation["operation"], operation["where"], operation["values"])
    expected = operation.get("expected_rows")
    if expected is not None and (isinstance(expected, bool) or not isinstance(expected, int)):
        raise UnsafeMutation("Invalid expected row count")
    stamp = int(time.time()) if now is None else now
    if expected is not None and expected > config.small_limit:
        if expected > config.absolute_limit or not nonce or not verifier_key or not backup_checker:
            raise ApprovalRequired("Signed human approval and independent backup required")
        # The only accepted backup digest is the one signed and stored by
        # the separate passkey gateway; never take it from the agent request.
        row = approval_store.db.execute(
            "SELECT payload,used FROM approvals WHERE nonce=?", (nonce,)
        ).fetchone()
        if not row or row[1]:
            raise ApprovalRequired("Approval missing or already consumed")
        approval = Approval(**json.loads(row[0]))
        if not backup_checker(operation, approval.backup_digest):
            raise ApprovalRequired("Backup not independently verified")
        if not approval_store.consume(nonce, operation, verifier_key, now=stamp):
            raise ApprovalRequired("Invalid, expired or replayed approval")
        # Committed consume is deliberate. Never retry on unknown DB outcome.
        approval_store.db.execute(
            "CREATE TABLE IF NOT EXISTS execution_events (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "nonce TEXT NOT NULL, phase TEXT NOT NULL, created_at INTEGER NOT NULL)"
        )
        approval_store.db.execute(
            "INSERT INTO execution_events(nonce,phase,created_at) VALUES(?,?,?)",
            (nonce, "claimed", stamp))
        try:
            count = apply(conn, change, config.schema,
                          primary_keys=config.primary_keys,
                          limit=expected, expected_rows=expected)
        except Exception:
            approval_store.db.execute(
                "INSERT INTO execution_events(nonce,phase,created_at) VALUES(?,?,?)",
                (nonce, "failed_or_unknown", stamp))
            raise
        approval_store.db.execute(
            "INSERT INTO execution_events(nonce,phase,created_at) VALUES(?,?,?)",
            (nonce, "committed", stamp))
        return count
    # A small operation requires no approval, but remains capped by the runner.
    return apply(conn, change, config.schema,
                 primary_keys=config.primary_keys, limit=config.small_limit,
                 expected_rows=expected)
