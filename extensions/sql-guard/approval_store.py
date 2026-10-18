"""Transactional, one-time approval store prototype.

Only run inside an independently authenticated approval service. Do not
expose token issuance or store access to the GPT agent.
"""
import json
import sqlite3
from dataclasses import asdict
from approval import Approval, verify_approval


class ApprovalStore:
    def __init__(self, path: str):
        self.db = sqlite3.connect(path, isolation_level=None, timeout=5)
        self.db.execute("CREATE TABLE IF NOT EXISTS approvals (nonce TEXT PRIMARY KEY, payload TEXT NOT NULL, used INTEGER NOT NULL DEFAULT 0)")

    def register(self, approval: Approval):
        self.db.execute("INSERT INTO approvals(nonce,payload,used) VALUES(?,?,0)",
                        (approval.nonce, json.dumps(asdict(approval), sort_keys=True)))

    def consume(self, nonce: str, operation: dict, secret: bytes, *, now: int) -> bool:
        """Atomic consume; caller must validate authenticated human before register.

        The approval must already exist; agent-supplied signed material alone
        cannot register a new approval.
        """
        try:
            self.db.execute("BEGIN IMMEDIATE")
            row = self.db.execute("SELECT payload,used FROM approvals WHERE nonce=?", (nonce,)).fetchone()
            if not row or row[1]:
                self.db.rollback()
                return False
            approval = Approval(**json.loads(row[0]))
            if not verify_approval(approval, operation, secret, set(), now=now):
                self.db.rollback()
                return False
            updated = self.db.execute("UPDATE approvals SET used=1 WHERE nonce=? AND used=0", (nonce,)).rowcount
            if updated != 1:
                self.db.rollback()
                return False
            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            raise

    def reserve_daily_budget(self, rows: int, *, now: int, daily_limit: int = 10) -> bool:
        """Atomically burn global UTC write allowance before touching MariaDB.

        Budget is intentionally not refunded if MariaDB fails: no ambiguity
        or retries can be used to increase the unapproved write allowance.
        """
        if (type(rows) is not int or type(now) is not int or type(daily_limit) is not int
                or rows < 0 or not 1 <= daily_limit <= 100 or rows > daily_limit):
            return False
        bucket = now // 86400
        try:
            self.db.execute("BEGIN IMMEDIATE")
            self.db.execute(
                "CREATE TABLE IF NOT EXISTS daily_write_budget "
                "(utc_day INTEGER PRIMARY KEY, rows_used INTEGER NOT NULL)"
            )
            self.db.execute(
                "INSERT OR IGNORE INTO daily_write_budget VALUES (?, 0)", (bucket,)
            )
            changed = self.db.execute(
                "UPDATE daily_write_budget SET rows_used=rows_used+? "
                "WHERE utc_day=? AND rows_used+? <= ?",
                (rows, bucket, rows, daily_limit),
            ).rowcount
            if changed != 1:
                self.db.rollback()
                return False
            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            raise

    def close(self):
        self.db.close()
