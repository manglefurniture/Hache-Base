#!/usr/bin/env bash
set -Eeuo pipefail

DB_HOST="${DB_HOST:-127.0.0.1}"
DB_USER="${DB_USER:-root}"
DB_NAME="${DB_NAME:-hache_base_test}"
MYSQL=(mariadb -N -B -h "$DB_HOST" -u "$DB_USER" "$DB_NAME")

sql() {
  "${MYSQL[@]}" -e "$1"
}

cleanup() {
  sql "DROP TABLE IF EXISTS ci_async_projection;" >/dev/null 2>&1 || true
  sql "DELETE FROM integration_inbox WHERE source = 'CI_P0_06';" >/dev/null 2>&1 || true
  sql "DELETE FROM integration_outbox WHERE idempotency_key LIKE 'ci-p0-06-%';" >/dev/null 2>&1 || true
  sql "DELETE FROM integration_idempotency_claims WHERE scope_name = 'CI_P0_06';" >/dev/null 2>&1 || true
}
trap cleanup EXIT
cleanup

# 1) Inbox dedupe: the same external event is stored once.
sql "INSERT INTO integration_inbox
  (source, external_event_id, event_type, aggregate_key, source_sequence, processing_status)
VALUES ('CI_P0_06', 'evt-duplicate', 'fixture.updated', 'agg-1', 10, 'received');"
sql "INSERT IGNORE INTO integration_inbox
  (source, external_event_id, event_type, aggregate_key, source_sequence, processing_status)
VALUES ('CI_P0_06', 'evt-duplicate', 'fixture.updated', 'agg-1', 10, 'received');"
count="$(sql "SELECT COUNT(*) FROM integration_inbox WHERE source='CI_P0_06' AND external_event_id='evt-duplicate';")"
test "$count" = "1"

# Opaque provider identities are exact: case and accents must not collapse.
sql "INSERT INTO integration_inbox
  (source, external_event_id, event_type, processing_status)
VALUES
  ('CI_P0_06', 'evt-case-A', 'fixture.identity', 'received'),
  ('CI_P0_06', 'evt-case-a', 'fixture.identity', 'received'),
  ('CI_P0_06', 'evt-accent-a', 'fixture.identity', 'received'),
  ('CI_P0_06', 'evt-accent-á', 'fixture.identity', 'received');"
identity_count="$(sql "SELECT COUNT(*) FROM integration_inbox WHERE source='CI_P0_06' AND event_type='fixture.identity';")"
test "$identity_count" = "4"

# 2) Outbox idempotency keys are also exact opaque identities.
sql "INSERT INTO integration_outbox
  (idempotency_key, event_type, aggregate_key, payload_json, operation_state)
VALUES
  ('ci-p0-06-Key-A', 'fixture.identity', 'agg-identity', '{}', 'requested'),
  ('ci-p0-06-Key-a', 'fixture.identity', 'agg-identity', '{}', 'requested'),
  ('ci-p0-06-key-á', 'fixture.identity', 'agg-identity', '{}', 'requested');"
outbox_identity_count="$(sql "SELECT COUNT(*) FROM integration_outbox WHERE event_type='fixture.identity';")"
test "$outbox_identity_count" = "3"

# The SQL state vocabulary is exact/case-sensitive, matching AsyncOperationState.
if sql "INSERT INTO integration_outbox
  (idempotency_key, event_type, aggregate_key, payload_json, operation_state)
VALUES ('ci-p0-06-uppercase-state', 'fixture.invalid', 'agg-invalid', '{}', 'REQUESTED');" >/dev/null 2>&1; then
  echo "uppercase outbox operation_state was accepted"
  exit 1
fi

# Concurrent outbox claim: only one worker can claim the same logical effect.
sql "INSERT INTO integration_outbox
  (idempotency_key, event_type, aggregate_key, payload_json, operation_state)
VALUES ('ci-p0-06-concurrent', 'fixture.notify', 'agg-1', '{}', 'requested');"

claim() {
  local token="$1"
  sql "UPDATE integration_outbox
      SET claim_token='${token}', claimed_at=UTC_TIMESTAMP(6), attempts=attempts+1
      WHERE idempotency_key='ci-p0-06-concurrent'
        AND operation_state IN ('requested','retry_pending')
        AND claim_token IS NULL
        AND dispatch_started_at IS NULL;"
}
claim worker_a &
pid_a=$!
claim worker_b &
pid_b=$!
wait "$pid_a"
wait "$pid_b"

claim_token="$(sql "SELECT claim_token FROM integration_outbox WHERE idempotency_key='ci-p0-06-concurrent';")"
case "$claim_token" in
  worker_a|worker_b) ;;
  *) echo "unexpected claim token: $claim_token"; exit 1 ;;
esac
attempts="$(sql "SELECT attempts FROM integration_outbox WHERE idempotency_key='ci-p0-06-concurrent';")"
test "$attempts" = "1"

# Once dispatch began, an unresolved attempt is not eligible for blind resend.
sql "UPDATE integration_outbox
  SET dispatch_started_at=UTC_TIMESTAMP(6), operation_state='outcome_unknown', claim_token=NULL
  WHERE idempotency_key='ci-p0-06-concurrent';"
sql "UPDATE integration_outbox
  SET claim_token='blind_retry'
  WHERE idempotency_key='ci-p0-06-concurrent'
    AND operation_state IN ('requested','retry_pending')
    AND claim_token IS NULL
    AND dispatch_started_at IS NULL;"
blind="$(sql "SELECT COALESCE(claim_token, '') FROM integration_outbox WHERE idempotency_key='ci-p0-06-concurrent';")"
test "$blind" = ""

# 3) Out-of-order event: a lower authoritative sequence cannot regress the projection.
sql "CREATE TABLE ci_async_projection (
  aggregate_key VARCHAR(191) NOT NULL PRIMARY KEY,
  source_sequence BIGINT UNSIGNED NOT NULL,
  value_text VARCHAR(64) NOT NULL
) ENGINE=InnoDB;"
sql "INSERT INTO ci_async_projection VALUES ('agg-ordered', 5, 'v5');"
sql "UPDATE ci_async_projection
  SET source_sequence=4, value_text='v4'
  WHERE aggregate_key='agg-ordered' AND source_sequence < 4;"
seq="$(sql "SELECT source_sequence FROM ci_async_projection WHERE aggregate_key='agg-ordered';")"
value="$(sql "SELECT value_text FROM ci_async_projection WHERE aggregate_key='agg-ordered';")"
test "$seq" = "5"
test "$value" = "v5"
sql "UPDATE ci_async_projection
  SET source_sequence=6, value_text='v6'
  WHERE aggregate_key='agg-ordered' AND source_sequence < 6;"
seq="$(sql "SELECT source_sequence FROM ci_async_projection WHERE aggregate_key='agg-ordered';")"
value="$(sql "SELECT value_text FROM ci_async_projection WHERE aggregate_key='agg-ordered';")"
test "$seq" = "6"
test "$value" = "v6"

# 4) Reprocess keeps the same row and idempotency key after reconciliation proves retry is safe.
sql "INSERT INTO integration_outbox
  (idempotency_key, event_type, aggregate_key, payload_json, operation_state, attempts, last_error_code)
VALUES ('ci-p0-06-reprocess', 'fixture.notify', 'agg-2', '{}', 'reconciling', 1, 'OUTCOME_NOT_FOUND');"
original_id="$(sql "SELECT id FROM integration_outbox WHERE idempotency_key='ci-p0-06-reprocess';")"
sql "UPDATE integration_outbox
  SET operation_state='retry_pending', last_error_code=NULL, dispatch_started_at=NULL, claim_token=NULL
  WHERE idempotency_key='ci-p0-06-reprocess' AND operation_state='reconciling';"
sql "UPDATE integration_outbox
  SET claim_token='reprocess_worker', claimed_at=UTC_TIMESTAMP(6), attempts=attempts+1
  WHERE idempotency_key='ci-p0-06-reprocess'
    AND operation_state='retry_pending'
    AND claim_token IS NULL
    AND dispatch_started_at IS NULL;"
same_id="$(sql "SELECT id FROM integration_outbox WHERE idempotency_key='ci-p0-06-reprocess';")"
test "$same_id" = "$original_id"
attempts="$(sql "SELECT attempts FROM integration_outbox WHERE idempotency_key='ci-p0-06-reprocess';")"
test "$attempts" = "2"

if sql "INSERT INTO integration_outbox
  (idempotency_key, event_type, aggregate_key, payload_json, operation_state)
VALUES ('ci-p0-06-reprocess', 'fixture.notify', 'agg-2', '{}', 'requested');" >/dev/null 2>&1; then
  echo "duplicate outbox idempotency key was accepted"
  exit 1
fi

# 5) Lightweight idempotency claim: duplicate claim does not create a second logical effect.
sql "INSERT INTO integration_idempotency_claims
  (scope_name, claim_key, operation_state, claim_token, attempts)
VALUES ('CI_P0_06', 'effect-1', 'requested', 'worker_a', 1);"
sql "INSERT IGNORE INTO integration_idempotency_claims
  (scope_name, claim_key, operation_state, claim_token, attempts)
VALUES ('CI_P0_06', 'effect-1', 'requested', 'worker_b', 1);"
claim_count="$(sql "SELECT COUNT(*) FROM integration_idempotency_claims WHERE scope_name='CI_P0_06' AND claim_key='effect-1';")"
test "$claim_count" = "1"
claim_owner="$(sql "SELECT claim_token FROM integration_idempotency_claims WHERE scope_name='CI_P0_06' AND claim_key='effect-1';")"
test "$claim_owner" = "worker_a"

# Claim scopes/keys are exact identities too.
sql "INSERT INTO integration_idempotency_claims
  (scope_name, claim_key, operation_state, claim_token, attempts)
VALUES
  ('CI_P0_06', 'effect-Key-A', 'requested', 'identity', 0),
  ('CI_P0_06', 'effect-Key-a', 'requested', 'identity', 0),
  ('CI_P0_06', 'effect-key-á', 'requested', 'identity', 0);"
claim_identity_count="$(sql "SELECT COUNT(*) FROM integration_idempotency_claims WHERE scope_name='CI_P0_06' AND claim_token='identity';")"
test "$claim_identity_count" = "3"

if sql "INSERT INTO integration_idempotency_claims
  (scope_name, claim_key, operation_state)
VALUES ('CI_P0_06', 'uppercase-state', 'REQUESTED');" >/dev/null 2>&1; then
  echo "uppercase claim operation_state was accepted"
  exit 1
fi

echo "INBOX_OUTBOX_IDEMPOTENCY_OK"
