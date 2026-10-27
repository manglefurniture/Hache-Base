#!/usr/bin/env python3
"""One-way, no-spend Clore consent exchange between isolated service accounts.

Telegram owns the signing key and its SQLite database. The finance account
owns the trusted public key and its separate financial ledger. Neither side
can read the other's database or key. A verified receipt is NOT a grant.
"""
import argparse
import json
import os
from pathlib import Path
import pwd
import re
import sqlite3
import stat
import subprocess
import sys
from urllib.parse import quote

from clore_consent_attestation import issue_receipt, record_verified_consent

MAX_RECEIPT_BYTES = 4096
FINANCE_TIMER = "hache-mining-operator-clore-cancel.timer"


class ExchangeError(ValueError):
    pass


def export_json(telegram_db, *, nonce, private_key_raw, now=None):
    """Generate only a signed receipt; never expose the private key."""
    receipt = issue_receipt(telegram_db, nonce=nonce,
                            private_key_raw=private_key_raw, now=now)
    return json.dumps(receipt, sort_keys=True, separators=(",", ":"))


def import_json(finance_db, *, wire, trusted_public_key_raw, reservation_id,
                now=None, timer_check=False):
    """Validate and consume exactly one attestation. Never authorize spend."""
    if type(wire) is not bytes or not 1 <= len(wire) <= MAX_RECEIPT_BYTES:
        raise ExchangeError("invalid_receipt_size")
    try:
        receipt = json.loads(wire.decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise ExchangeError("invalid_receipt_json") from exc
    if type(receipt) is not dict:
        raise ExchangeError("invalid_receipt_shape")
    result = record_verified_consent(
        finance_db, receipt=receipt, trusted_public_key_raw=trusted_public_key_raw,
        reservation_id=reservation_id, now=now, timer_check=timer_check)
    if result.get("rental_permitted") is not False or result.get("provider_mutation") is not False:
        raise ExchangeError("unexpected_financial_permission")
    return {"consent_recorded": True, "rental_permitted": False,
            "provider_mutation": False}


def _account(name):
    try:
        uid = pwd.getpwnam(name).pw_uid
    except KeyError as exc:
        raise ExchangeError("service_account_missing") from exc
    if os.geteuid() != uid:
        raise ExchangeError("wrong_service_identity")


def _checked_regular(path, *, owner_uid, private=False):
    """No symlink, shared-writable parent, hardlink, or permissive key."""
    path = Path(path)
    parent = path.parent.stat(follow_symlinks=False)
    if (not stat.S_ISDIR(parent.st_mode) or parent.st_mode & 0o022):
        raise ExchangeError("unsafe_parent_directory")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    fd = os.open(path, flags)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != owner_uid or
                info.st_nlink != 1 or info.st_mode & 0o022 or
                (private and info.st_mode & 0o077)):
            raise ExchangeError("unsafe_file_ownership_or_mode")
        return fd
    except Exception:
        os.close(fd)
        raise


def _read_key(path, *, owner_uid, private):
    fd = _checked_regular(path, owner_uid=owner_uid, private=private)
    with os.fdopen(fd, "rb") as handle:
        raw = handle.read(33)
    if len(raw) != 32:
        raise ExchangeError("invalid_ed25519_key_size")
    return raw


def _open_db(path, *, uid, readonly):
    path = Path(path)
    fd = _checked_regular(path, owner_uid=uid)
    os.close(fd)
    mode = "ro" if readonly else "rw"
    uri = "file:" + quote(str(path.resolve()), safe="/") + "?mode=" + mode
    db = sqlite3.connect(uri, uri=True, isolation_level=None, timeout=5)
    db.execute("PRAGMA busy_timeout=5000")
    return db


def main(argv=None):
    parser = argparse.ArgumentParser(description="Clore signed consent only; NEVER rents")
    subs = parser.add_subparsers(dest="action", required=True)
    exp = subs.add_parser("export", help="Run as hache-telegram; JSON receipt on stdout")
    exp.add_argument("--db", required=True)
    exp.add_argument("--nonce", required=True)
    exp.add_argument("--private-key", required=True)
    imp = subs.add_parser("import", help="Run as hache-miner; JSON receipt on stdin")
    imp.add_argument("--db", required=True)
    imp.add_argument("--reservation-id", required=True)
    imp.add_argument("--public-key", required=True)
    args = parser.parse_args(argv)
    try:
        if args.action == "export":
            _account("hache-telegram")
            key = _read_key(args.private_key, owner_uid=os.geteuid(), private=True)
            with _open_db(args.db, uid=os.geteuid(), readonly=True) as db:
                result = export_json(db, nonce=args.nonce, private_key_raw=key)
            print(result)
        else:
            _account("hache-miner")
            if not re.fullmatch(r"[0-9a-f]{32}", args.reservation_id):
                raise ExchangeError("invalid_reservation_id")
            key = _read_key(args.public_key, owner_uid=0, private=False)
            wire = sys.stdin.buffer.read(MAX_RECEIPT_BYTES + 1)
            timer_ok = subprocess.run(
                ["systemctl", "is-active", "--quiet", FINANCE_TIMER],
                capture_output=True, check=False, timeout=5).returncode == 0
            with _open_db(args.db, uid=os.geteuid(), readonly=False) as db:
                result = import_json(
                    db, wire=wire, trusted_public_key_raw=key,
                    reservation_id=args.reservation_id, timer_check=timer_ok)
            print(json.dumps(result, sort_keys=True))
    except (OSError, ValueError, sqlite3.Error, subprocess.TimeoutExpired) as exc:
        # Return error classes, never key contents, tokens or signed payloads.
        print("CLORE_CONSENT_EXCHANGE_DENIED=" + type(exc).__name__, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
