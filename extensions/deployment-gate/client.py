#!/usr/bin/env python3
"""Nonprivileged deployment gate client (never includes a credential or root shell)."""
import argparse
import json
import socket
import sys

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('request',help='JSON object: capabilities, prepare, execute or status')
    p.add_argument('--socket',default='/run/hache-deploy-gate/agent.sock')
    args=p.parse_args()
    try:
        request=json.loads(args.request)
        if not isinstance(request,dict):
            raise ValueError('expected_json_object')
        blob=(json.dumps(request,sort_keys=True,separators=(',',':'))+'\n').encode()
        if len(blob)>8192:
            raise ValueError('oversized_request')
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as sock:
            sock.settimeout(180)
            sock.connect(args.socket)
            sock.sendall(blob)
            with sock.makefile('rb') as reader:
                raw=reader.readline(32769)
        answer=json.loads(raw)
        print(json.dumps(answer,sort_keys=True,indent=2))
        return 0 if answer.get('ok') is True else 2
    except (OSError,ValueError,KeyError):
        print('DEPLOY_GATE_UNAVAILABLE',file=sys.stderr)
        return 2

if __name__=='__main__':
    sys.exit(main())
