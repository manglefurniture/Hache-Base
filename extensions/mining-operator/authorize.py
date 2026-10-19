#!/usr/bin/env python3
"""Root-only: bind a user's exact mining instruction to a prepared one-use plan."""
import argparse
import grp
import json
import os
from pathlib import Path
import re
import sqlite3
import time

from broker import canonical, digest, protected_json

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--config', required=True)
parser.add_argument('--plan-id', required=True)
parser.add_argument('--expected-digest', required=True)
parser.add_argument('--approve', action='store_true', help='Only after the owner authorized this exact instruction')
args = parser.parse_args()
if os.geteuid() != 0:
    parser.error('root required')
if not re.fullmatch(r'[a-f0-9]{32}', args.plan_id) or not re.fullmatch(r'[a-f0-9]{64}', args.expected_digest):
    parser.error('invalid plan or digest')
cfg = protected_json(args.config)
db = sqlite3.connect('file:'+cfg['database']+'?mode=ro', uri=True)
try:
    row = db.execute('SELECT operation,snapshot,digest,expires,phase FROM plans WHERE id=?', (args.plan_id,)).fetchone()
finally:
    db.close()
if not row or row[4] != 'prepared' or row[3] <= int(time.time()):
    parser.error('plan unavailable or expired')
bound = {'operation': json.loads(row[0]), 'snapshot': json.loads(row[1])}
if digest(bound) != row[2] or row[2] != args.expected_digest:
    parser.error('digest mismatch')
print(json.dumps({'plan_id': args.plan_id, **bound, 'expires_at': row[3]}, indent=2))
if args.approve:
    path = Path(cfg['grants'])
    info = path.lstat()
    if not path.is_dir() or path.is_symlink() or info.st_uid != 0 or info.st_mode & 0o022:
        parser.error('grant directory not root controlled')
    target = path/(args.plan_id+'.json')
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write(canonical({'plan_id': args.plan_id, 'digest': row[2], 'expires_at': row[3]})+'\n')
        os.fchown(stream.fileno(), 0, grp.getgrnam(cfg['service_group']).gr_gid)
        os.fchmod(stream.fileno(), 0o640)
    print('EXACT_ONE_USE_GRANT_CREATED')
