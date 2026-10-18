"""Independently verified, root-owned backup attestation for SQL Guard.

Agent-supplied checksums are not proof. The approval service verifies the
requested digest against a root-owned manifest and a gzip archive it can read.
Production requires owner_uid=0 and non-writable root-controlled directories.
"""
import gzip
import hashlib
import json
import os
import re
import stat
import time


def _safe_regular(path: str, owner_uid: int) -> bool:
    try:
        s = os.lstat(path)
        return (stat.S_ISREG(s.st_mode) and s.st_uid == owner_uid
                and not (s.st_mode & 0o022))
    except OSError:
        return False


def _safe_dir(path: str, owner_uid: int) -> bool:
    try:
        s = os.lstat(path)
        return (stat.S_ISDIR(s.st_mode) and s.st_uid == owner_uid
                and not (s.st_mode & 0o022))
    except OSError:
        return False


def verify_backup(operation: dict, digest: str, *, manifest_path: str,
                  archive_dir: str, owner_uid: int = 0, max_age: int = 3600,
                  now: int | None = None) -> bool:
    """Only trust a recent root-owned archive and strict manifest.

    Must be stored outside any directory editable by gpt-agent. Never pass
    owner_uid from HTTP requests; it is test-only configurability.
    """
    current = int(time.time()) if now is None else now
    if not _safe_dir(archive_dir, owner_uid):
        return False
    if not _safe_regular(manifest_path, owner_uid):
        return False
    if not re.fullmatch(r"[a-f0-9]{64}", digest):
        return False
    try:
        with open(manifest_path, encoding="utf-8") as f:
            metadata = json.load(f)
        name = metadata["archive"]
        if not isinstance(name, str) or not name.endswith(".sql.gz") or not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", name):
            return False
        if metadata["sha256"] != digest:
            return False
        created = metadata["created_at"]
        if not isinstance(created, int) or not 0 <= current-created <= max_age:
            return False
        if operation["database"] not in metadata["databases"]:
            return False
        path = os.path.join(archive_dir, name)
        if not _safe_regular(path, owner_uid):
            return False
        if not _safe_dir(os.path.dirname(manifest_path), owner_uid):
            return False
        sha = hashlib.sha256()
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(fd, "rb") as f:
            for data in iter(lambda: f.read(1024 * 1024), b""):
                sha.update(data)
            if sha.hexdigest() != digest:
                return False
            f.seek(0)
            with gzip.GzipFile(fileobj=f, mode="rb") as archive:
                for _ in iter(lambda: archive.read(1024 * 1024), b""):
                    pass
        return True
    except (OSError, ValueError, TypeError, KeyError, EOFError, gzip.BadGzipFile):
        return False
