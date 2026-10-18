"""Fail-closed policy decisions for structured database operations.

This library does NOT execute SQL or protect direct database credentials.
Only a privilege-separated execution service can enforce its decisions.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Decision(str, Enum):
    ALLOW = "allow"
    APPROVAL_REQUIRED = "approval_required"
    DENY = "deny"


@dataclass(frozen=True)
class Request:
    operation: str
    database: str
    affected_rows: Optional[int] = None
    has_where: bool = False
    backed_up: bool = False
    approved: bool = False


SAFE_READ = frozenset({"select", "show", "explain"})
WRITES = frozenset({"insert", "update", "delete"})
DESTRUCTIVE = frozenset({"drop", "truncate", "replace_database", "restore", "alter_destructive"})


def decide(request: Request, allowed_databases: set[str], threshold: int = 10) -> Decision:
    """Decision only: approved=True must come from a trusted approval store, not GPT."""
    if threshold < 1 or request.database not in allowed_databases:
        return Decision.DENY
    operation = request.operation.lower()
    if operation in SAFE_READ:
        return Decision.ALLOW
    if operation in DESTRUCTIVE:
        return (Decision.ALLOW if request.approved and request.backed_up
                else Decision.APPROVAL_REQUIRED)
    if operation not in WRITES:
        return Decision.DENY
    if request.affected_rows is None or request.affected_rows < 0:
        return Decision.DENY
    if operation in {"update", "delete"} and not request.has_where:
        return Decision.APPROVAL_REQUIRED
    if request.affected_rows > threshold:
        return (Decision.ALLOW if request.approved and request.backed_up
                else Decision.APPROVAL_REQUIRED)
    return Decision.ALLOW
