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

# Canonical COM-001 trace fields must exist and be required on the communication record.
required_not_null="$(query "SELECT COUNT(*)
  FROM information_schema.columns
  WHERE table_schema = DATABASE()
    AND table_name = 'email_delivery_messages'
    AND is_nullable = 'NO'
    AND column_name IN (
      'channel', 'provider', 'local_message_key', 'business_operation_id',
      'template_key', 'template_version', 'recipient_normalized',
      'delivery_status', 'attempt_count', 'status_occurred_at', 'requested_at'
    );")"
test "$required_not_null" = "11"

# Requested is a durable local intent. provider_message_id is unknown until provider acceptance.
query "INSERT INTO email_delivery_messages
  (channel, provider, local_message_key, business_operation_id, template_key, template_version,
   recipient_normalized, provider_message_id, delivery_status, attempt_count, status_occurred_at, requested_at)
  VALUES
  ('email', 'resend-p1-08-fixture', 'message-key-001', 'business-op-001', 'registration-confirmation', 'v1',
   'person@example.test', NULL, 'requested', 1, '2026-09-04 11:59:59.000000', '2026-09-04 11:59:59.000000');"

# The same logical message key cannot be inserted twice (send-side dedupe contract).
if query "INSERT INTO email_delivery_messages
  (channel, provider, local_message_key, business_operation_id, template_key, template_version,
   recipient_normalized, delivery_status, attempt_count, status_occurred_at, requested_at)
  VALUES
  ('email', 'resend-p1-08-fixture', 'message-key-001', 'business-op-001', 'registration-confirmation', 'v1',
   'person@example.test', 'requested', 1, '2026-09-04 11:59:59.000000', '2026-09-04 11:59:59.000000');" >/dev/null 2>&1; then
  echo 'ERROR: duplicate local_message_key was accepted' >&2
  exit 1
fi

# Provider API acceptance sets provider_message_id but does not claim delivery.
query "UPDATE email_delivery_messages
  SET provider_message_id='email-001',
      delivery_status='accepted',
      status_occurred_at='2026-09-04 12:00:00.000000',
      accepted_at='2026-09-04 12:00:00.000000'
  WHERE provider='resend-p1-08-fixture' AND local_message_key='message-key-001';"

status="$(query "SELECT delivery_status FROM email_delivery_messages WHERE provider='resend-p1-08-fixture' AND local_message_key='message-key-001';")"
test "$status" = "accepted"

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
    AND delivery_status IN ('requested', 'accepted', 'delayed')
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
    AND delivery_status IN ('requested', 'accepted')
    AND status_occurred_at < '2026-09-04 12:01:00.000000';"

status="$(query "SELECT delivery_status FROM email_delivery_messages WHERE provider='resend-p1-08-fixture' AND provider_message_id='email-001';")"
test "$status" = "delivered"

# Reprocess is the same inbox row/event. It increments inbox attempts; it never creates a new send.
query "UPDATE integration_inbox
  SET processing_status='retry_pending', attempts=attempts+1, last_error_code='fixture_retry'
  WHERE source='resend-p1-08-fixture' AND external_event_id='svix-delivered-001';"
query "UPDATE integration_inbox
  SET processing_status='processed', processed_at=NOW(6), last_error_code=NULL
  WHERE source='resend-p1-08-fixture' AND external_event_id='svix-delivered-001';"

inbox_attempts="$(query "SELECT attempts FROM integration_inbox WHERE source='resend-p1-08-fixture' AND external_event_id='svix-delivered-001';")"
test "$inbox_attempts" = "1"
send_attempts="$(query "SELECT attempt_count FROM email_delivery_messages WHERE provider='resend-p1-08-fixture' AND provider_message_id='email-001';")"
test "$send_attempts" = "1"
rows="$(query "SELECT COUNT(*) FROM integration_inbox WHERE source='resend-p1-08-fixture';")"
test "$rows" = "2"

# Suppression is an explicit provider-supported terminal state.
query "INSERT INTO email_delivery_messages
  (channel, provider, local_message_key, business_operation_id, template_key, template_version,
   recipient_normalized, provider_message_id, delivery_status, attempt_count,
   status_occurred_at, requested_at, suppressed_at)
  VALUES
  ('email', 'resend-p1-08-fixture', 'message-key-suppressed', 'business-op-002', 'registration-confirmation', 'v1',
   'blocked@example.test', 'email-suppressed-001', 'suppressed', 1,
   '2026-09-04 12:03:00.000000', '2026-09-04 12:02:59.000000', '2026-09-04 12:03:00.000000');"

# The projection vocabulary excludes engagement events such as opened.
if query "INSERT INTO email_delivery_messages
  (channel, provider, local_message_key, business_operation_id, template_key, template_version,
   recipient_normalized, delivery_status, attempt_count, status_occurred_at, requested_at)
  VALUES
  ('email', 'resend-p1-08-fixture', 'invalid-opened', 'business-op-invalid', 'template', 'v1',
   'person@example.test', 'opened', 1, '2026-09-04 12:03:00.000000', '2026-09-04 12:03:00.000000');" >/dev/null 2>&1; then
  echo 'ERROR: email_delivery_messages accepted an unsupported status' >&2
  exit 1
fi

query "DELETE FROM integration_inbox WHERE source = 'resend-p1-08-fixture';"
query "DELETE FROM email_delivery_messages WHERE provider = 'resend-p1-08-fixture';"

echo "EMAIL_DELIVERY_MARIADB_OK"
