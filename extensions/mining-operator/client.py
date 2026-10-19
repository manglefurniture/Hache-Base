#!/usr/bin/env python3
"""Send one structured mining operation to the local broker. No credentials."""
import argparse
import json
import socket
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--socket', default='/run/hache-mining-operator/agent.sock')
parser.add_argument('request', help='JSON request; no SQL, URLs, secrets or shell commands')
args = parser.parse_args()
try:
    payload = json.dumps(json.loads(args.request), separators=(',', ':')).encode()+b'\n'
    if len(payload) > 8192:
        raise ValueError('request too large')
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        # Miner installation can take longer than read-only provider calls,
        # but the independent Vast financial watchdog is not run here.
        connection.settimeout(320)
        connection.connect(args.socket)
        connection.sendall(payload)
        raw = connection.makefile('rb').readline(131073)
        if len(raw) > 131072:
            raise ValueError('response too large')
        response = json.loads(raw)
    print(json.dumps(response, indent=2))
    raise SystemExit(0 if response.get('ok') else 2)
except (OSError, ValueError):
    print(json.dumps({'ok': False, 'error': 'operator_connection_unavailable'}))
    raise SystemExit(2)
