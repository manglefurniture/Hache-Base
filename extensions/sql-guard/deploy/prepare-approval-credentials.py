#!/usr/bin/env python3
"""Provision isolated SQL Guard approval credentials; no HTTP/SQL services start.

Runs on the VPS as root, offline. A single-use enrollment token is held only
in a root-readable local file, never printed to logs or the ChatGPT connector.
"""
import argparse
import hashlib
import os
from pathlib import Path
import secrets
import stat

ENV_DIR = Path("/etc/sqlguard")
ENV_PATH = ENV_DIR / "approval.env"
TOKEN_PATH = Path("/root/sqlguard-enrollment-token")
RELEASE_CODE = Path("/opt/sqlguard/current/extensions/sql-guard/approval_web.py")
RP_ID = "aprobaciones.hacheinteractive.com"


def create_material():
    bootstrap_token = secrets.token_urlsafe(32)
    values = {
        "SQLGUARD_DB_PATH": "/var/lib/sqlguard/approvals.sqlite",
        "SQLGUARD_RP_ID": RP_ID,
        "SQLGUARD_ORIGIN": "https://" + RP_ID,
        "SQLGUARD_OWNER_ID": secrets.token_hex(16),
        "SQLGUARD_SIGN_KEY_HEX": secrets.token_hex(32),
        "SQLGUARD_BOOTSTRAP_HASH": hashlib.sha256(
            bootstrap_token.encode("ascii")).hexdigest(),
        "SQLGUARD_AGENT_TOKEN": secrets.token_urlsafe(32),
        "SQLGUARD_BACKUP_MANIFEST": "/var/lib/sqlguard-trusted/manifest.json",
        "SQLGUARD_BACKUP_DIRECTORY": "/var/lib/sqlguard-trusted",
    }
    env_content = "".join(f"{key}={value}\n" for key, value in values.items())
    return env_content, bootstrap_token + "\n"


def require_private_directory(path, owner_uid=0):
    s = path.lstat()
    if not stat.S_ISDIR(s.st_mode) or s.st_uid != owner_uid or s.st_mode & 0o077:
        raise RuntimeError(f"Directory must be owner-only and root-owned: {path}")


def safe_create(path, content, owner_uid=0):
    """O_EXCL prevents replacing existing files or following destination symlinks."""
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                 getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        os.fchmod(fd, 0o600)
        if os.fstat(fd).st_uid != owner_uid:
            raise RuntimeError("Unexpected owner on newly-created private file")
        with os.fdopen(fd, "w", encoding="ascii") as stream:
            fd = -1
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        if fd >= 0:
            os.close(fd)


def create_pair(env_path, token_path, env_content, token_content, owner_uid=0):
    """Atomic no-overwrite staging, with best-effort cleanup of partial failure."""
    if os.path.lexists(env_path) or os.path.lexists(token_path):
        raise FileExistsError("Approval credentials already exist; do not overwrite")
    created = []
    try:
        safe_create(token_path, token_content, owner_uid)
        created.append(token_path)
        safe_create(env_path, env_content, owner_uid)
        created.append(env_path)
    except BaseException:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="Read-only check; default")
    parser.add_argument("--apply", action="store_true",
                        help="Root only: create new credentials without overwriting")
    args = parser.parse_args()
    if args.apply and args.check:
        parser.error("Use only one mode")

    if args.check or not args.apply:
        print("Approval environment:", "PRESENT" if os.path.lexists(ENV_PATH) else "ABSENT")
        print("Local enrollment token:", "PRESENT" if os.path.lexists(TOKEN_PATH) else "ABSENT")
        print("CHECK_ONLY: no changes")
        return

    if os.geteuid() != 0:
        raise SystemExit("ERROR: root is required for --apply")
    require_private_directory(ENV_DIR)
    require_private_directory(Path("/root"))
    release_stat = RELEASE_CODE.stat()
    if not stat.S_ISREG(release_stat.st_mode) or release_stat.st_uid != 0:
        raise RuntimeError("Versioned root-owned SQL Guard code must be installed")
    if release_stat.st_mode & 0o022:
        raise RuntimeError("Versioned SQL Guard code must not be group/world writable")
    if os.path.lexists(ENV_PATH) or os.path.lexists(TOKEN_PATH):
        raise SystemExit("ERROR: existing approval files; refusing overwrite")
    previous_umask = os.umask(0o077)
    try:
        env_content, token_content = create_material()
        create_pair(ENV_PATH, TOKEN_PATH, env_content, token_content)
    finally:
        os.umask(previous_umask)
    print("APPROVAL_CREDENTIALS_READY")
    print("Private configuration: /etc/sqlguard/approval.env")
    print("One-time enrollment token: /root/sqlguard-enrollment-token")
    print("Token never printed; read locally via ConnectBot only when enrolling.")
    print("NOT STARTED: approval service, runner, Nginx or MariaDB changes")


if __name__ == "__main__":
    main()
