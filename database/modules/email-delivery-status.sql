-- OPTIONAL Hache-Base P1-08 projection for transactional email delivery status.
-- This is NOT a migration and MUST NOT be applied globally.
-- It depends conceptually on P0-06 integration_inbox for verified-event dedupe,
-- processing attempts and safe reprocess. The communication record deliberately
-- minimizes content, but COM-001 still requires a normalized recipient and trace metadata.

CREATE TABLE IF NOT EXISTS email_delivery_messages (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    channel VARCHAR(32) COLLATE utf8mb4_nopad_bin NOT NULL DEFAULT 'email',
    provider VARCHAR(80) COLLATE utf8mb4_nopad_bin NOT NULL,
    local_message_key VARCHAR(191) COLLATE utf8mb4_nopad_bin NOT NULL,
    business_operation_id VARCHAR(191) COLLATE utf8mb4_nopad_bin NOT NULL,
    template_key VARCHAR(191) COLLATE utf8mb4_nopad_bin NOT NULL,
    template_version VARCHAR(80) COLLATE utf8mb4_nopad_bin NOT NULL,
    recipient_normalized VARCHAR(320) NOT NULL,
    provider_message_id VARCHAR(191) COLLATE utf8mb4_nopad_bin NULL,
    delivery_status VARCHAR(32) COLLATE utf8mb4_nopad_bin NOT NULL DEFAULT 'requested',
    attempt_count INT UNSIGNED NOT NULL DEFAULT 0,
    status_occurred_at DATETIME(6) NOT NULL,
    requested_at DATETIME(6) NOT NULL,
    accepted_at DATETIME(6) NULL,
    delivered_at DATETIME(6) NULL,
    delayed_at DATETIME(6) NULL,
    bounced_at DATETIME(6) NULL,
    failed_at DATETIME(6) NULL,
    suppressed_at DATETIME(6) NULL,
    last_provider_event_id VARCHAR(191) COLLATE utf8mb4_nopad_bin NULL,
    last_error_code VARCHAR(128) NULL,
    request_id VARCHAR(128) NULL,
    correlation_id VARCHAR(128) NULL,
    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uq_email_delivery_message_key (channel, local_message_key),
    UNIQUE KEY uq_email_delivery_provider_message (provider, provider_message_id),
    INDEX idx_email_delivery_business_operation (business_operation_id, id),
    INDEX idx_email_delivery_recipient (recipient_normalized, id),
    INDEX idx_email_delivery_status_time (delivery_status, status_occurred_at, id),
    CONSTRAINT chk_email_delivery_channel CHECK (channel = 'email'),
    CONSTRAINT chk_email_delivery_status CHECK (
        delivery_status IN (
            'requested',
            'accepted',
            'delayed',
            'delivered',
            'bounced',
            'failed',
            'suppressed'
        )
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- COM-001 trace record:
-- - local_message_key identifies one logical notification and is the local dedupe key;
-- - business_operation_id links the notification to the durable business event/CUF;
-- - template_key/template_version make the rendered contract reviewable;
-- - recipient_normalized is required communication metadata and is PII: projects must define
--   access, retention and deletion. Do not replace it with the full body or arbitrary payload;
-- - attempt_count is the send-attempt count. Webhook processing attempts live separately in
--   integration_inbox.attempts.
-- provider_message_id is nullable while status=requested and should be set when the provider
-- accepts the send. A provider API 2xx/message ID moves requested -> accepted; it is not delivery.

-- Webhook events belong in integration_inbox using:
--   source             = provider (for P1-08 reference adapter: 'resend')
--   external_event_id  = verified Svix message id / provider event id
--   event_type         = provider event type
--   aggregate_key      = provider_message_id
--   occurred_at        = provider event timestamp
--   payload_sha256     = hash of the raw verified payload
-- The raw webhook body may contain additional PII and is deliberately not required by this schema.
-- Reprocess MUST reuse the same integration_inbox row/external_event_id and increment inbox attempts;
-- it is not a request to send a second email. A new send is a new logical operation/outbox entry.
-- Hard bounce/suppression are never a reason for blind resend; retry policy must classify the
-- original send failure and preserve the same logical idempotency contract.
--
-- Do not add a foreign key from integration_inbox.aggregate_key to this table: a verified
-- provider webhook may race the local projection/acceptance write. Projects should reconcile
-- that race transactionally and apply provider event time/state rules before changing status.
