"""Experimental MariaDB executor, NOT a production service.

Requires a dedicated limited DB-API connection. Do not expose this connection
to the GPT Linux account. Small UPDATE/DELETE only; no arbitrary SQL.
"""
import re
from dataclasses import dataclass
from typing import Any, Mapping

from policy import Decision, Request, decide


class UnsafeMutation(PermissionError):
    pass


def _name(value: str, allow: set[str]) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value) or value not in allow:
        raise UnsafeMutation("Identifier not allowed")
    return "`" + value + "`"


@dataclass(frozen=True)
class Change:
    database: str
    table: str
    operation: str
    where: Mapping[str, Any]
    values: Mapping[str, Any]


def apply(conn, change: Change, schema: Mapping[str, Mapping[str, set[str]]], *, limit: int = 10) -> int:
    """Run a small guarded mutation using a MariaDB-compatible DB-API connection.

    BEGIN/SELECT FOR UPDATE keep the matching rows locked during the update.
    Restrict the SQL connection to InnoDB databases. No approval mechanism is
    implemented; larger mutations are *always* refused.
    """
    if limit < 1 or change.operation not in {"update", "delete"}:
        raise UnsafeMutation("Unsupported operation")
    if change.database not in schema or change.table not in schema[change.database]:
        raise UnsafeMutation("Database/table not allowed")
    columns = schema[change.database][change.table]
    if not change.where or (change.operation == "update" and not change.values):
        raise UnsafeMutation("Predicate and update values required")
    table = _name(change.table, set(schema[change.database]))
    db = _name(change.database, set(schema))
    parts = sorted(change.where.items())
    where = " AND ".join(f"{_name(k, columns)} <=> %s" for k, _ in parts)
    args = [v for _, v in parts]
    set_parts = sorted(change.values.items())
    setters = ", ".join(f"{_name(k, columns)} = %s" for k, _ in set_parts)
    cur = conn.cursor()
    try:
        cur.execute("START TRANSACTION")
        # Fetch at most limit+1 matching rows; refuse large operations, with
        # a consistent row-lock snapshot for the matching rows.
        cur.execute(f"SELECT 1 FROM {db}.{table} WHERE {where} LIMIT %s FOR UPDATE", args + [limit + 1])
        rows = cur.fetchall()
        count = len(rows)
        if decide(Request(change.operation, change.database, count, True), set(schema), limit) != Decision.ALLOW:
            raise UnsafeMutation("Approval-only operation is disabled")
        if change.operation == "delete":
            cur.execute(f"DELETE FROM {db}.{table} WHERE {where}", args)
        else:
            cur.execute(f"UPDATE {db}.{table} SET {setters} WHERE {where}", [v for _, v in set_parts] + args)
        # UPDATE rowcount may reflect changed rather than matched rows.
        if cur.rowcount > count:
            raise UnsafeMutation("Unexpected affected rows")
        if change.operation == "delete" and cur.rowcount != count:
            raise UnsafeMutation("Deleted-row count mismatch")
        conn.commit()
        return count
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
