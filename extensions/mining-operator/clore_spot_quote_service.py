#!/usr/bin/env python3
"""Root-installed, unprivileged Clore Spot quote socket.

The only permitted action is a fixed, credentialed GET for one provider
server ID. Only the private Telegram service UID may submit requests.
No rentals, bids, provider writes, shell, file writes or root grants.
"""
import json
import os
import pwd
import socket
import socketserver
import struct
import time

from clore_spot_quote import fetch_spot, credential, SpotError

MAX_REQUEST = 256
MAX_RESPONSE = 4096
MIN_INTERVAL = 2.0

class ServiceError(ValueError):
    pass

def process(request, key, *, fetcher=fetch_spot):
    if (type(request) is not dict or set(request) != {"server_id"} or
            type(request["server_id"]) is not int or
            not 0 < request["server_id"] < 10**15):
        raise ServiceError("invalid_quote_request")
    result = fetcher(request["server_id"], key)
    if (type(result) is not dict or result.get("server_id") != request["server_id"] or
            result.get("rental_permitted") is not False or
            result.get("executable_quote") is not False):
        raise ServiceError("unsafe_quote_result")
    return {"ok": True, "result": result}

class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        try:
            creds = struct.unpack("3i", self.connection.getsockopt(
                socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
            if creds[1] != self.server.telegram_uid:
                raise ServiceError("not_authorized")
            self.connection.settimeout(18)
            raw = self.rfile.readline(MAX_REQUEST + 1)
            if not raw.endswith(b"\n") or len(raw) > MAX_REQUEST:
                raise ServiceError("invalid_request_size")
            now = time.monotonic()
            if now - self.server.last_call < MIN_INTERVAL:
                raise ServiceError("rate_limit")
            # Reserve the slot before reaching the external provider.
            self.server.last_call = now
            try:
                req = json.loads(raw)
            except (UnicodeError, ValueError):
                raise ServiceError("invalid_json") from None
            reply = process(req, self.server.clore_key)
        except (ServiceError, SpotError) as exc:
            reply = {"ok": False, "error": str(exc)}
        except Exception:
            # Provider returns and credentials must never enter the socket or logs.
            reply = {"ok": False, "error": "quote_unavailable"}
        blob = (json.dumps(reply, sort_keys=True, separators=(",", ":")) + "\n").encode()
        if len(blob) > MAX_RESPONSE:
            blob = b'{"ok":false,"error":"quote_too_large"}\n'
        try:
            self.wfile.write(blob)
        except OSError:
            pass

def main():
    if os.environ.get("LISTEN_FDS") != "1" or os.environ.get("LISTEN_PID") != str(os.getpid()):
        raise RuntimeError("systemd_socket_activation_required")
    key = credential()
    telegram_uid = pwd.getpwnam("hache-telegram").pw_uid
    # systemd owns FD 3 and the socket path; Python never changes its permissions.
    server = socketserver.UnixStreamServer("", Handler, bind_and_activate=False)
    server.socket.close()
    server.socket = socket.socket(fileno=3)
    server.telegram_uid = telegram_uid
    server.clore_key = key
    server.last_call = -MIN_INTERVAL
    server.serve_forever(poll_interval=0.2)

if __name__ == "__main__":
    main()
