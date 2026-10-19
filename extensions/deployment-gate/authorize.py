#!/usr/bin/env python3
"""Root-only authorization for one exact deployment after owner CI verification.

Never called by gpt-agent. A chat confirmation is not a root grant until
trusted approval infrastructure independently binds it to this plan.
"""
import argparse
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import time

from deploy_gate import TARGETS,compact,fingerprint,trusted_json


def authorize(cfg, plan_id, expected_digest, expected_target, expected_commit,
              expected_sha256, *, confirmed_ci=False):
    if os.geteuid()!=0:
        raise ValueError('root_required')
    if not confirmed_ci:
        raise ValueError('owner_must_verify_merge_ci_and_archive')
    if not re.fullmatch('[a-f0-9]{32}',plan_id) or not re.fullmatch('[a-f0-9]{64}',expected_digest):
        raise ValueError('invalid_plan')
    db=sqlite3.connect('file:'+cfg['database']+'?mode=ro',uri=True)
    try:
        row=db.execute('SELECT operation,snapshot,digest,expires,phase FROM deploy_plans WHERE id=?',
                       (plan_id,)).fetchone()
    finally:
        db.close()
    if not row or row[4]!='prepared' or row[3]<=int(time.time()):
        raise ValueError('plan_expired_or_unavailable')
    operation=json.loads(row[0])
    snapshot=json.loads(row[1])
    if (operation.get('target')!=expected_target or
            operation.get('commit')!=expected_commit or
            operation.get('archive_sha256')!=expected_sha256 or
            fingerprint({'operation':operation,'snapshot':snapshot})!=row[2] or
            row[2]!=expected_digest or
            snapshot.get('repository')!=TARGETS[expected_target]['repo']):
        raise ValueError('owner_review_did_not_match_plan')
    grants=Path(cfg['grants'])
    owner=grants.lstat()
    if (not stat.S_ISDIR(owner.st_mode) or owner.st_uid!=0 or
            owner.st_mode & 0o022 or grants.is_symlink()):
        raise ValueError('unsafe_grant_directory')
    dest=grants/(plan_id+'.json')
    flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0)
    fd=os.open(dest,flags,0o600)
    with os.fdopen(fd,'w') as handle:
        handle.write(compact({'plan_id':plan_id,'digest':row[2],
                              'expires_at':row[3]})+'\n')
        handle.flush()
        os.fsync(handle.fileno())
    return {'status':'ONE_USE_DEPLOY_APPROVED','target':expected_target,
            'commit':expected_commit,'expires_at':row[3]}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',default='/etc/hache-deploy-gate/config.json')
    p.add_argument('--plan-id',required=True)
    p.add_argument('--expected-digest',required=True)
    p.add_argument('--target',choices=sorted(TARGETS),required=True)
    p.add_argument('--commit',required=True)
    p.add_argument('--archive-sha256',required=True)
    p.add_argument('--owner-verified-ci',action='store_true',
                   help='Owner independently confirmed merged GitHub commit, CI and archive provenance')
    args=p.parse_args()
    try:
        cfg=trusted_json(args.config)
        result=authorize(cfg,args.plan_id,args.expected_digest,
                         args.target,args.commit,args.archive_sha256,
                         confirmed_ci=args.owner_verified_ci)
        print(compact(result))
    except (ValueError,sqlite3.Error,KeyError,OSError) as err:
        p.error(str(err))


if __name__=='__main__':
    main()
