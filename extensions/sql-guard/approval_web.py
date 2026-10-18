"""Experimental HTTPS approval UI; no SQL execution and no default backup bypass.

Deploy only behind an HTTPS reverse proxy as a separate system account.
The agent API token may stage requests, but MUST NOT approve any request.
"""
import hmac
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
        req = gateway_obj.db.execute(
            "SELECT operation_json,backup_digest FROM requests WHERE id=?",
            (body["request_id"],)).fetchone()
        if not req:
            abort(404)
        import json
        allowed = verify_backup(json.loads(req[0]), req[1])
        gateway_obj.finish_approval(
            body["request_id"], body["challenge"], body["credential"],
            int(time.time()), backup_is_verified=allowed)
        return jsonify({"status": "approved"})

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
    return create_app({key: os.getenv("SQLGUARD_" + key) for key in keys},
                      backup_checker=checker)
