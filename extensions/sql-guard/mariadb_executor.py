"""Experimental MariaDB executor with bounded primary-key mutations.

Must run in an isolated limited-privilege service, never in gpt-agent.
Only small, typed UPDATE and DELETE operations; larger changes always denied.
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


def apply(conn, change: Change, schema: Mapping[str, Mapping[str, set[str]]],
          *, primary_keys: Mapping[str, Mapping[str, str]],
          limit: int = 10) -> int:
    """Apply only primary-key rows observed and locked in this transaction.

    The trusted configuration MUST name a genuine single-column PRIMARY KEY of
    an InnoDB table. Composite PKs, views and other engines are unsupported.
    A future deployment must audit the actual schema and trigger effects.
    """
    if limit < 1 or change.operation not in {"update", "delete"}:
        raise UnsafeMutation("Unsupported operation")
    if change.database not in schema or change.table not in schema[change.database]:
        raise UnsafeMutation("Database/table not allowed")
    columns = schema[change.database][change.table]
    pk = primary_keys.get(change.database, {}).get(change.table)
    if pk is None or pk not in columns:
        raise UnsafeMutation("A configured primary key is required")
    if not change.where or (change.operation == "update" and not change.values):
        raise UnsafeMutation("Predicate and update values required")
    if change.operation == "update" and pk in change.values:
        raise UnsafeMutation("Primary key cannot be changed")
    table = _name(change.table, set(schema[change.database]))
    db = _name(change.database, set(schema))
    primary = _name(pk, columns)
    parts = sorted(change.where.items())
    where = " AND ".join(f"{_name(k, columns)} <=> %s" for k, _ in parts)
    args = [v for _, v in parts]
    set_parts = sorted(change.values.items())
    setters = ", ".join(f"{_name(k, columns)} = %s" for k, _ in set_parts)
    cur = conn.cursor()
    try:
        cur.execute("START TRANSACTION")
        cur.execute(
            f"SELECT {primary} FROM {db}.{table} WHERE {where} "
            f"ORDER BY {primary} LIMIT %s FOR UPDATE",
            args + [limit + 1])
        keys = [row[0] for row in cur.fetchall()]
        count = len(keys)
        if decide(Request(change.operation, change.database, count, True),
                  set(schema), limit) != Decision.ALLOW:
            raise UnsafeMutation("Mass or unscoped operation denied")
        if count == 0:
            conn.commit()
            return 0
        holders = ",".join(["%s"] * count)
        target = f"{primary} IN ({holders})"
        if change.operation == "delete":
            cur.execute(f"DELETE FROM {db}.{table} WHERE {target}", keys)
        else:
            cur.execute(
                f"UPDATE {db}.{table} SET {setters} WHERE {target}",
                [v for _, v in set_parts] + keys)
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
