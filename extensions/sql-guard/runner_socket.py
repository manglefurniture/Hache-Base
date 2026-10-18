"""UNIX-socket API for a separate, restricted SQL Guard runner account.

Agent never receives SQL credentials or the signing key. Only structured,
allowlisted operations are accepted; no arbitrary SQL command endpoint.
This is a deployable prototype, not yet approved for production use.
"""
import json
import os
import socket
import socketserver
import struct
import stat
from typing import Callable

from approval_store import ApprovalStore
from authorized_runner import RunnerConfig, execute_guarded
from backup_attestation import verify_backup


class RunnerServer(socketserver.UnixStreamServer):
    request_queue_size = 8
    def __init__(self, path: str, execute_callback: Callable, *, allowed_uid: int | None = None):
        self.execute_callback = execute_callback
        self.allowed_uid = allowed_uid
        super().__init__(path, RunnerHandler)


class RunnerHandler(socketserver.StreamRequestHandler):
    def handle(self):
        self.request.settimeout(10)
        try:
            if self.server.allowed_uid is not None:
                cred = self.request.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
                peer_uid = struct.unpack("3i", cred)[1]
                if peer_uid != self.server.allowed_uid:
                    raise PermissionError("Peer UID not authorized")
            raw = self.rfile.readline(8193)
            if not raw or len(raw) > 8192 or not raw.endswith(b"\n"):
                raise ValueError("Malformed or oversized request")
            payload = json.loads(raw)
            if (not isinstance(payload, dict) or set(payload) != {"operation", "nonce"}
                    or not isinstance(payload["operation"], dict)
                    or not (payload["nonce"] is None or
                            isinstance(payload["nonce"], str) and
                            len(payload["nonce"]) <= 128)):
                raise ValueError("Unexpected request structure")
            count = self.server.execute_callback(payload["operation"], payload["nonce"])
            answer = {"ok": True, "affected_rows": count}
        except Exception:
            # Client never receives secrets, SQL exception details, or backups.
            answer = {"ok": False, "error": "Operation rejected"}
        self.wfile.write((json.dumps(answer) + "\n").encode())


class IsolatedExecutor:
    """Each request uses a new DB connection, approval-store handle and lock."""
    def __init__(self, *, connect_db, approval_store_path: str, schema: dict,
                 primary_keys: dict, verifier_key: bytes,
                 backup_manifest: str, backup_directory: str):
        self.connect_db = connect_db
        self.store_path = approval_store_path
        self.config = RunnerConfig(schema, primary_keys)
        self.verifier_key = verifier_key
        self.manifest = backup_manifest
        self.directory = backup_directory

    def __call__(self, operation: dict, nonce: str | None) -> int:
        connection = self.connect_db()
        store = None
        try:
            store = ApprovalStore(self.store_path)
            return execute_guarded(
                connection, store, operation, config=self.config,
                nonce=nonce, verifier_key=self.verifier_key,
                backup_checker=lambda op, digest: verify_backup(
                    op, digest, manifest_path=self.manifest,
                    archive_dir=self.directory, owner_uid=0))
        finally:
            if store is not None:
                store.close()
            connection.close()


def _require_root_controlled(path: str) -> None:
    s = os.lstat(path)
    if (not stat.S_ISREG(s.st_mode) or s.st_uid != 0
            or (s.st_mode & 0o022)):
        raise RuntimeError("Allowlist must be a root-owned, non-writable regular file")


def run_from_env():
    """Only run as sqlguard-runner, on a root-protected /run/sqlguard socket path."""
    import pymysql

    required = [
        "SQLGUARD_RUNNER_SOCKET", "SQLGUARD_RUNNER_ALLOWLIST",
        "SQLGUARD_RUNNER_DB_USER", "SQLGUARD_RUNNER_DB_PASSWORD",
        "SQLGUARD_SIGN_KEY_HEX", "SQLGUARD_DB_PATH",
        "SQLGUARD_BACKUP_MANIFEST", "SQLGUARD_BACKUP_DIRECTORY",
        "SQLGUARD_RUNNER_ALLOWED_AGENT_UID", "SQLGUARD_RUNNER_SOCKET_GROUP_GID",
    ]
    env = {k: os.environ.get(k) for k in required}
    if any(not v for v in env.values()):
        raise RuntimeError("SQL Guard runner configuration incomplete")
    signing_key = bytes.fromhex(env["SQLGUARD_SIGN_KEY_HEX"])
    if len(signing_key) < 32:
        raise RuntimeError("Signing key too short")
    allowlist_path = env["SQLGUARD_RUNNER_ALLOWLIST"]
    _require_root_controlled(allowlist_path)
    with open(allowlist_path, encoding="utf-8") as stream:
        data = json.load(stream)
    if set(data) != {"schema", "primary_keys"}:
        raise RuntimeError("Unexpected allowlist configuration")
    path = env["SQLGUARD_RUNNER_SOCKET"]
    folder = os.path.dirname(path)
    fs = os.stat(folder)
    if (not stat.S_ISDIR(fs.st_mode) or fs.st_uid != 0
            or (fs.st_mode & 0o002)):
        raise RuntimeError("Socket directory not root controlled")
    if os.path.lexists(path):
        raise RuntimeError("Socket already exists; operator must inspect it")
    connect = lambda: pymysql.connect(
        unix_socket="/run/mysqld/mysqld.sock",
        user=env["SQLGUARD_RUNNER_DB_USER"],
        password=env["SQLGUARD_RUNNER_DB_PASSWORD"],
        autocommit=True, connect_timeout=5, read_timeout=20, write_timeout=20)
    executor = IsolatedExecutor(
        connect_db=connect, approval_store_path=env["SQLGUARD_DB_PATH"],
        schema={db: {table: set(cols) for table, cols in tables.items()}
                for db, tables in data["schema"].items()},
        primary_keys=data["primary_keys"], verifier_key=signing_key,
        backup_manifest=env["SQLGUARD_BACKUP_MANIFEST"],
        backup_directory=env["SQLGUARD_BACKUP_DIRECTORY"])
    previous_umask = os.umask(0o117)
    try:
        with RunnerServer(path, executor,
                          allowed_uid=int(env["SQLGUARD_RUNNER_ALLOWED_AGENT_UID"])) as server:
            os.chown(path, -1, int(env["SQLGUARD_RUNNER_SOCKET_GROUP_GID"]))
            os.chmod(path, 0o660)
            try:
                server.serve_forever(poll_interval=0.5)
            finally:
                os.unlink(path)
    finally:
        os.umask(previous_umask)


if __name__ == "__main__":
    run_from_env()
