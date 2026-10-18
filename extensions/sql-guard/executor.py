"""Constrained SQL update/delete executor. Works with a trusted DB-API connection.

No free-form SQL. The connection MUST belong to a dedicated database role;
this module cannot protect against bypass through a direct SQL client.
"""
import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from policy import Decision, Request, decide

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class GuardRejected(PermissionError):
    pass


@dataclass(frozen=True)
class Mutation:
    database: str
    table: str
    operation: str
    predicate: Mapping[str, Any]
    values: Mapping[str, Any]


def _identifier(value: str, allowlist: set[str]) -> str:
    if not _IDENTIFIER.fullmatch(value) or value not in allowlist:
        raise GuardRejected("Unknown identifier")
    return "`" + value + "`"


def execute_mutation(
    conn,
    request: Mutation,
    *,
    tables: Mapping[str, Mapping[str, set[str]]],
    threshold: int = 10,
    placeholder: str = "?",
) -> int:
    """Apply small changes only. Reject mass operations; do not trust agent approvals.

    The caller must provide a separate, authorized connection. Atomic counting
    requires a transaction and suitable isolation provided by the database.
    This prototype is intended for SQLite integration tests, NOT production.
    """
    if request.operation not in ("update", "delete"):
        raise GuardRejected("Unsupported operation")
    if request.database not in tables or request.table not in tables[request.database]:
        raise GuardRejected("Unknown database or table")
    allowed_columns = tables[request.database][request.table]
    if not request.predicate or (request.operation == "update" and not request.values):
        raise GuardRejected("Empty predicate or values")
    if placeholder not in ("?", "%s"):
        raise GuardRejected("Unsupported placeholder")
    table = _identifier(request.table, set(tables[request.database]))
    where_items = sorted(request.predicate.items())
    predicate = " AND ".join(
        f"{_identifier(k, allowed_columns)} = {placeholder}" for k, _ in where_items
    )
    where_values = [v for _, v in where_items]
    cursor = conn.cursor()
    try:
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE {predicate}", where_values)
        count = cursor.fetchone()[0]
        decision = decide(Request(request.operation, request.database, count, True), set(tables), threshold)
        if decision != Decision.ALLOW:
            raise GuardRejected(f"Operation rejected: {decision.value}")
        if request.operation == "delete":
            cursor.execute(f"DELETE FROM {table} WHERE {predicate}", where_values)
        else:
            changes = sorted(request.values.items())
            setters = ", ".join(f"{_identifier(k, allowed_columns)} = {placeholder}" for k, _ in changes)
            cursor.execute(
                f"UPDATE {table} SET {setters} WHERE {predicate}",
                [v for _, v in changes] + where_values,
            )
        if cursor.rowcount != count:
            raise GuardRejected("Unexpected affected-row count")
        conn.commit()
        return count
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
