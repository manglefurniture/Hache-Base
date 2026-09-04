#!/usr/bin/env bash
set -Eeuo pipefail

DB_HOST="${DB_HOST:-127.0.0.1}"
DB_USER="${DB_USER:-root}"
DB_NAME="${DB_NAME:-hache_base_test}"
MYSQL=(mariadb -N -B -h "$DB_HOST" -u "$DB_USER" "$DB_NAME")

query() {
  "${MYSQL[@]}" -e "$1"
}

query "DELETE FROM integration_inbox WHERE source = 'resend-p1-08-fixture';"
query "DELETE FROM email_delivery_messages WHERE provider = 'resend-p1-08-fixture';"

query "INSERT INTO email_delivery_messages
  (provider, provider_message_id, local_message_key, delivery_status, status_occurred_at, accepted_at)
  VALUES
  ('resend-p1-08-fixture', 'email-001', 'business-message-001', 'accepted', '2026-09-04 12:00:00.000000', '2026-09-04 12:00:00.000000');"

query "INSERT INTO integration_inbox
  (source, external_event_id, event_type, aggregate_key, occurred_at, payload_sha256, processing_status)
  VALUES
  ('resend-p1-08-fixture', 'svix-delivered-001', 'email.delivered', 'email-001', '2026-09-04 12:02:00.000000', REPEAT('a', 64), 'received');"

# Same provider event must dedupe instead of creating a second effect.
query "INSERT IGNORE INTO integration_inbox
  (source, external_event_id, event_type, aggregate_key, occurred_at, payload_sha256, processing_status)
  VALUES
  ('resend-p1-08-fixture', 'svix-delivered-001', 'email.delivered', 'email-001', '2026-09-04 12:02:00.000000', REPEAT('a', 64), 'received');"

delivered_event_count="$(query "SELECT COUNT(*) FROM integration_inbox WHERE source='resend-p1-08-fixture' AND external_event_id='svix-delivered-001';")"
test "$delivered_event_count" = "1"

query "UPDATE email_delivery_messages
  SET delivery_status='delivered',
      status_occurred_at='2026-09-04 12:02:00.000000',
      delivered_at='2026-09-04 12:02:00.000000',
      last_provider_event_id='svix-delivered-001'
  WHERE provider='resend-p1-08-fixture'
    AND provider_message_id='email-001'
    AND status_occurred_at < '2026-09-04 12:02:00.000000';"

query "INSERT INTO integration_inbox
  (source, external_event_id, event_type, aggregate_key, occurred_at, payload_sha256, processing_status)
  VALUES
  ('resend-p1-08-fixture', 'svix-delayed-stale-001', 'email.delivery_delayed', 'email-001', '2026-09-04 12:01:00.000000', REPEAT('b', 64), 'received');"

# A late-arriving older delayed event must not degrade delivered.
query "UPDATE email_delivery_messages
  SET delivery_status='delayed',
      status_occurred_at='2026-09-04 12:01:00.000000',
      delayed_at='2026-09-04 12:01:00.000000',
      last_provider_event_id='svix-delayed-stale-001'
  WHERE provider='resend-p1-08-fixture'
    AND provider_message_id='email-001'
    AND status_occurred_at < '2026-09-04 12:01:00.000000';"

status="$(query "SELECT delivery_status FROM email_delivery_messages WHERE provider='resend-p1-08-fixture' AND provider_message_id='email-001';")"
test "$status" = "delivered"

# Reprocess is the same inbox row/event. It increments attempts; it never creates a new send.
query "UPDATE integration_inbox
  SET processing_status='retry_pending', attempts=attempts+1, last_error_code='fixture_retry'
  WHERE source='resend-p1-08-fixture' AND external_event_id='svix-delivered-001';"
query "UPDATE integration_inbox
  SET processing_status='processed', processed_at=NOW(6), last_error_code=NULL
  WHERE source='resend-p1-08-fixture' AND external_event_id='svix-delivered-001';"

attempts="$(query "SELECT attempts FROM integration_inbox WHERE source='resend-p1-08-fixture' AND external_event_id='svix-delivered-001';")"
test "$attempts" = "1"
rows="$(query "SELECT COUNT(*) FROM integration_inbox WHERE source='resend-p1-08-fixture';")"
test "$rows" = "2"

# The projection vocabulary is intentionally limited to P1-08 delivery states.
if query "INSERT INTO email_delivery_messages
  (provider, provider_message_id, delivery_status, status_occurred_at)
  VALUES ('resend-p1-08-fixture', 'invalid-opened', 'opened', '2026-09-04 12:03:00.000000');" >/dev/null 2>&1; then
  echo 'ERROR: email_delivery_messages accepted an unsupported status' >&2
  exit 1
fi

query "DELETE FROM integration_inbox WHERE source = 'resend-p1-08-fixture';"
query "DELETE FROM email_delivery_messages WHERE provider = 'resend-p1-08-fixture';"

echo "EMAIL_DELIVERY_MARIADB_OK"
