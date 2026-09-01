-- OPTIONAL Hache-Base module for asynchronous integration delivery.
-- P0-06 template: inbox, outbox and lightweight idempotency claims.
-- This is NOT a migration and MUST NOT be applied globally.
-- Adopt only in projects whose CUFs/integrations justify persistent dedupe/retry.

CREATE TABLE IF NOT EXISTS integration_inbox (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    source VARCHAR(80) NOT NULL,
    external_event_id VARCHAR(191) NOT NULL,
    event_type VARCHAR(128) NOT NULL,
    aggregate_key VARCHAR(191) NULL,
    source_sequence BIGINT UNSIGNED NULL,
    occurred_at DATETIME(6) NULL,
    payload_sha256 CHAR(64) NULL,
    processing_status VARCHAR(32) NOT NULL DEFAULT 'received',
    attempts INT UNSIGNED NOT NULL DEFAULT 0,
    claim_token VARCHAR(64) NULL,
    claimed_at DATETIME(6) NULL,
    processed_at DATETIME(6) NULL,
    next_attempt_at DATETIME(6) NULL,
    last_error_code VARCHAR(128) NULL,
    request_id VARCHAR(128) NULL,
    correlation_id VARCHAR(128) NULL,
    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uq_integration_inbox_source_event (source, external_event_id),
    INDEX idx_integration_inbox_work (processing_status, next_attempt_at, id),
    INDEX idx_integration_inbox_aggregate_sequence (aggregate_key, source_sequence)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS integration_outbox (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    idempotency_key VARCHAR(191) NOT NULL,
    event_type VARCHAR(128) NOT NULL,
    aggregate_key VARCHAR(191) NULL,
    payload_json LONGTEXT NOT NULL,
    operation_state VARCHAR(32) NOT NULL DEFAULT 'requested',
    attempts INT UNSIGNED NOT NULL DEFAULT 0,
    available_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    claim_token VARCHAR(64) NULL,
    claimed_at DATETIME(6) NULL,
    dispatch_started_at DATETIME(6) NULL,
    confirmed_at DATETIME(6) NULL,
    provider_operation_id VARCHAR(191) NULL,
    last_error_code VARCHAR(128) NULL,
    request_id VARCHAR(128) NULL,
    correlation_id VARCHAR(128) NULL,
    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uq_integration_outbox_idempotency (idempotency_key),
    INDEX idx_integration_outbox_work (operation_state, available_at, id),
    INDEX idx_integration_outbox_aggregate (aggregate_key, id),
    CONSTRAINT chk_integration_outbox_operation_state CHECK (
        operation_state IN (
            'requested',
            'accepted',
            'outcome_unknown',
            'retry_pending',
            'reconciling',
            'confirmed',
            'failed_final',
            'cancelled'
        )
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS integration_idempotency_claims (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    scope_name VARCHAR(80) NOT NULL,
    claim_key VARCHAR(191) NOT NULL,
    operation_state VARCHAR(32) NOT NULL DEFAULT 'requested',
    attempts INT UNSIGNED NOT NULL DEFAULT 0,
    claim_token VARCHAR(64) NULL,
    claimed_at DATETIME(6) NULL,
    effect_started_at DATETIME(6) NULL,
    confirmed_at DATETIME(6) NULL,
    outcome_reference VARCHAR(191) NULL,
    last_error_code VARCHAR(128) NULL,
    request_id VARCHAR(128) NULL,
    correlation_id VARCHAR(128) NULL,
    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uq_integration_claim_scope_key (scope_name, claim_key),
    INDEX idx_integration_claim_state (operation_state, id),
    CONSTRAINT chk_integration_claim_operation_state CHECK (
        operation_state IN (
            'requested',
            'accepted',
            'outcome_unknown',
            'retry_pending',
            'reconciling',
            'confirmed',
            'failed_final',
            'cancelled'
        )
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
