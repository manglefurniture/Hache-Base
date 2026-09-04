-- OPTIONAL Hache-Base P1-08 projection for transactional email delivery status.
-- This is NOT a migration and MUST NOT be applied globally.
-- It depends conceptually on P0-06 integration_inbox for verified-event dedupe,
-- processing attempts and safe reprocess. No raw webhook payload or recipient PII is required here.

CREATE TABLE IF NOT EXISTS email_delivery_messages (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    provider VARCHAR(80) COLLATE utf8mb4_nopad_bin NOT NULL,
    provider_message_id VARCHAR(191) COLLATE utf8mb4_nopad_bin NOT NULL,
    local_message_key VARCHAR(191) COLLATE utf8mb4_nopad_bin NULL,
    delivery_status VARCHAR(32) COLLATE utf8mb4_nopad_bin NOT NULL DEFAULT 'accepted',
    status_occurred_at DATETIME(6) NOT NULL,
    accepted_at DATETIME(6) NULL,
    delivered_at DATETIME(6) NULL,
    delayed_at DATETIME(6) NULL,
    bounced_at DATETIME(6) NULL,
    failed_at DATETIME(6) NULL,
    last_provider_event_id VARCHAR(191) COLLATE utf8mb4_nopad_bin NULL,
    last_error_code VARCHAR(128) NULL,
    request_id VARCHAR(128) NULL,
    correlation_id VARCHAR(128) NULL,
    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uq_email_delivery_provider_message (provider, provider_message_id),
    INDEX idx_email_delivery_local_message (local_message_key, id),
    INDEX idx_email_delivery_status_time (delivery_status, status_occurred_at, id),
    CONSTRAINT chk_email_delivery_status CHECK (
        delivery_status IN ('accepted', 'delivered', 'delayed', 'bounced', 'failed')
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Webhook events belong in integration_inbox using:
--   source             = provider (for P1-08 reference adapter: 'resend')
--   external_event_id  = verified Svix message id / provider event id
--   event_type         = provider event type
--   aggregate_key      = provider_message_id
--   occurred_at        = provider event timestamp
--   payload_sha256     = hash of the raw verified payload
-- The raw webhook body may contain PII and is deliberately not required by this schema.
-- Reprocess MUST reuse the same integration_inbox row/external_event_id and increment attempts;
-- it is not a request to send a second email. A new send is a new logical operation/outbox entry.
--
-- Do not add a foreign key from integration_inbox.aggregate_key to this table: a verified
-- provider webhook may race the local projection/acceptance write. Projects should reconcile
-- that race transactionally and apply provider event time/order rules before changing status.
