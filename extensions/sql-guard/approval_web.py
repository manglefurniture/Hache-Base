"""Experimental HTTPS approval UI; no SQL execution and no default backup bypass.

Deploy only behind an HTTPS reverse proxy as a separate system account.
The agent API token may stage requests, but MUST NOT approve any request.
"""
import hmac
import hashlib
import os
import re
import time
from urllib.parse import urlparse

from flask import Flask, abort, g, jsonify, render_template, request

from passkey_gateway import CeremonyRejected, PasskeyGateway


def create_app(config: dict, backup_checker=None):
    required = ["DB_PATH", "RP_ID", "ORIGIN", "OWNER_ID", "SIGN_KEY_HEX",
                "BOOTSTRAP_HASH", "AGENT_TOKEN"]
    if any(not config.get(key) for key in required):
        raise RuntimeError("Missing SQL Guard gateway settings")
    if len(config["AGENT_TOKEN"]) < 32 or not os.path.isabs(config["DB_PATH"]):
        raise RuntimeError("Insecure gateway configuration")
    signing_key = bytes.fromhex(config["SIGN_KEY_HEX"])
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["TRUSTED_HOSTS"] = [urlparse(config["ORIGIN"]).netloc]
    app.config["MAX_CONTENT_LENGTH"] = 16384
    app.config["PROPAGATE_EXCEPTIONS"] = False
    # None is a deliberate fail-closed default; never trust a client flag.
    verify_backup = backup_checker if backup_checker is not None else (
        lambda *_args: False)

    def gateway():
        if "gateway" not in g:
            g.gateway = PasskeyGateway(
                config["DB_PATH"], rp_id=config["RP_ID"],
                origin=config["ORIGIN"], owner_id=config["OWNER_ID"],
                signing_key=signing_key, bootstrap_hash=config["BOOTSTRAP_HASH"])
        return g.gateway

    @app.teardown_appcontext
    def cleanup(exception):
        db = g.pop("gateway", None)
        if db:
            db.close()

    @app.after_request
    def headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; script-src 'self'; style-src 'self'; "
            "connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")
        return response

    @app.before_request
    def check_origin():
        if request.method == "POST":
            if request.path.startswith("/api/agent/"):
                token = request.headers.get("Authorization", "")
                if not hmac.compare_digest(token, "Bearer " + config["AGENT_TOKEN"]):
                    abort(401)
            elif request.headers.get("Origin") != config["ORIGIN"]:
                abort(403)

    @app.errorhandler(CeremonyRejected)
    def rejected(err):
        return jsonify({"error": "Request rejected"}), 403

    @app.errorhandler(ValueError)
    def invalid(err):
        return jsonify({"error": "Invalid request"}), 400

    @app.get("/verify-passkey")
    def passkey_check_page():
        return render_template("passkey_check.html")

    @app.post("/api/passkey-check/start")
    def passkey_check_start():
        return jsonify(gateway().begin_passkey_check(int(time.time())))

    @app.post("/api/passkey-check/finish")
    def passkey_check_finish():
        body = request.get_json()
        gateway().finish_passkey_check(
            body["challenge"], body["credential"], int(time.time()))
        return jsonify({"status": "verified", "grants_issued": 0})

    @app.get("/enroll")
    def enroll_page():
        return render_template("approval.html", mode="enroll", request_id="")

    @app.get("/approve/<request_id>")
    def approve_page(request_id):
        if not re.fullmatch(r"[a-zA-Z0-9_-]{20,128}", request_id):
            abort(404)
        gateway().pending(request_id, int(time.time()))
        return render_template("approval.html", mode="approve", request_id=request_id)

    @app.get("/api/pending/<request_id>")
    def pending(request_id):
        return jsonify(gateway().pending(request_id, int(time.time())))

    @app.post("/api/agent/stage")
    def stage():
        body = request.get_json(force=False, silent=False)
        rid = gateway().stage_request(body["operation"], body["backup_digest"], int(time.time()))
        return jsonify({"request_id": rid, "url": config["ORIGIN"] + "/approve/" + rid}), 201

    @app.get("/api/agent/status/<request_id>")
    def status(request_id):
        token = request.headers.get("Authorization", "")
        if not hmac.compare_digest(token, "Bearer " + config["AGENT_TOKEN"]):
            abort(401)
        row = gateway().db.execute(
            "SELECT r.expires,r.approved,r.approval_nonce,a.payload,a.used "
            "FROM requests r LEFT JOIN approvals a ON a.nonce=r.approval_nonce "
            "WHERE r.id=?", (request_id,)).fetchone()
        if not row:
            abort(404)
        timestamp = int(time.time())
        if row[0] <= timestamp:
            return jsonify({"status": "expired"})
        if not row[1]:
            return jsonify({"status": "pending"})
        if not row[3]:
            return jsonify({"status": "unavailable"})
        import json
        grant = json.loads(row[3])
        if grant["expires_at"] <= timestamp:
            return jsonify({"status": "expired"})
        if row[4]:
            return jsonify({"status": "consumed"})
        # Nonce is only disclosed to the authenticated agent after the
        # passkey owner has signed the exact operation.
        return jsonify({"status": "approved", "nonce": row[2]})

    @app.post("/api/enroll/start")
    def enroll_start():
        body = request.get_json()
        return jsonify(gateway().begin_enrollment(body["bootstrap_token"], int(time.time())))

    @app.post("/api/enroll/finish")
    def enroll_finish():
        body = request.get_json()
        gateway().finish_enrollment(body["challenge"], body["credential"], int(time.time()))
        return jsonify({"status": "enrolled"})

    @app.post("/api/approve/start")
    def approve_start():
        return jsonify(gateway().begin_approval(request.get_json()["request_id"], int(time.time())))

    @app.post("/api/approve/finish")
    def approve_finish():
        body = request.get_json()
        gateway_obj = gateway()
        gateway_obj.finish_approval(
            body["request_id"], body["challenge"], body["credential"],
            int(time.time()), backup_checker=verify_backup)
        return jsonify({"status": "approved"})


    @app.before_request
    def root_window_authentication():
        """Separate strong owner secret before any WebAuthn ceremony quota is charged.

        The browser uses HTTPS Basic auth; passkey verification is still
        mandatory on every enable/disable. No token is given to the agent.
        """
        if request.path != "/root-window" and not request.path.startswith("/api/root-window/"):
            return None
        secret_digest = config.get("ROOT_WINDOW_OWNER_AUTH_SHA256")
        if not isinstance(secret_digest, str) or len(secret_digest) != 64 or any(c not in "0123456789abcdef" for c in secret_digest):
            abort(503)
        authorization=request.authorization
        valid = (authorization is not None and authorization.type.lower() == "basic"
                 and authorization.username == "owner"
                 and isinstance(authorization.password,str)
                 and len(authorization.password) >= 32)
        password = authorization.password if valid else ""
        digest=hashlib.sha256(password.encode("utf-8")).hexdigest()
        if not valid or not hmac.compare_digest(digest,secret_digest):
            return ("Autenticación del propietario requerida",401,
                    {"WWW-Authenticate":'Basic realm="Hache Owner", charset="UTF-8"',
                     "Cache-Control":"no-store"})
        return None

    def root_window_setup():
        secret = config.get("ROOT_WINDOW_KEY_HEX")
        endpoint = config.get("ROOT_WINDOW_SOCKET")
        if not secret or endpoint != "/run/hache-root-window/admin.sock":
            abort(503)
        try:
            key = bytes.fromhex(secret)
        except ValueError:
            abort(503)
        if len(key) != 32:
            abort(503)
        return key, endpoint

    def root_window_send(body):
        import json
        import socket
        _, endpoint = root_window_setup()
        message = json.dumps(body,sort_keys=True,separators=(",",":")).encode() + b"\n"
        try:
            with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as peer:
                peer.settimeout(3)
                peer.connect(endpoint)
                peer.sendall(message)
                result = b""
                while b"\n" not in result and len(result) <= 4096:
                    part = peer.recv(1024)
                    if not part:
                        break
                    result += part
            if len(result) > 4096:
                abort(503)
            outcome = json.loads(result)
        except (OSError, ValueError, TypeError):
            abort(503)
        if not isinstance(outcome,dict) or not outcome.get("ok"):
            abort(503)
        return outcome["result"]

    @app.get("/root-window")
    def root_window_page():
        root_window_setup()
        return render_template("root_window.html")

    @app.get("/api/root-window/status")
    def root_window_status():
        return jsonify(root_window_send({"method":"status"}))

    @app.post("/api/root-window/start")
    def root_window_begin():
        root_window_setup()
        body = request.get_json(silent=True) or {}
        return jsonify(gateway().begin_root_window(
            body.get("action"),int(time.time()),
            scope=body.get("scope","restart_operator"),
            duration_minutes=body.get("duration_minutes",10)))

    @app.post("/api/root-window/finish")
    def root_window_end():
        key, _ = root_window_setup()
        body = request.get_json(silent=True) or {}
        ticket = gateway().finish_root_window(
            body.get("action"),body.get("challenge"),body.get("credential"),
            int(time.time()),window_key=key,
            scope=body.get("scope","restart_operator"),
            duration_minutes=body.get("duration_minutes",10))
        # Ticket never reaches browser or nonprivileged agent.
        return jsonify(root_window_send({"ticket":ticket}))

    return app


def create_app_from_env():
    from backup_attestation import verify_backup

    keys = ["DB_PATH","RP_ID","ORIGIN","OWNER_ID","SIGN_KEY_HEX",
            "BOOTSTRAP_HASH","AGENT_TOKEN"]
    manifest = os.getenv("SQLGUARD_BACKUP_MANIFEST")
    directory = os.getenv("SQLGUARD_BACKUP_DIRECTORY")
    checker = None
    if manifest and directory:
        # The user operating the service cannot forge a root-owned manifest.
        checker = lambda operation, digest: verify_backup(
            operation, digest, manifest_path=manifest, archive_dir=directory,
            owner_uid=0)
    config = {key: os.getenv("SQLGUARD_" + key) for key in keys}
    config["ROOT_WINDOW_KEY_HEX"] = os.getenv("SQLGUARD_ROOT_WINDOW_KEY_HEX")
    config["ROOT_WINDOW_SOCKET"] = os.getenv("SQLGUARD_ROOT_WINDOW_SOCKET")
    config["ROOT_WINDOW_OWNER_AUTH_SHA256"] = os.getenv("SQLGUARD_ROOT_WINDOW_OWNER_AUTH_SHA256")
    return create_app(config, backup_checker=checker)
