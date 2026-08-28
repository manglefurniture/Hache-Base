-- Plantilla opcional: versionado inmutable de credenciales de pasarelas de pago.
-- Adaptar nombres y relaciones al dominio del proyecto antes de convertirla en migración.
-- Requiere que la aplicación cifre secretos con una clave maestra externa a la BD.

CREATE TABLE IF NOT EXISTS payment_gateway_credentials (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    provider VARCHAR(40) NOT NULL,
    environment VARCHAR(30) NOT NULL DEFAULT 'PRODUCTION',
    public_key VARCHAR(255) NULL,
    access_token_enc TEXT NOT NULL,
    -- NULL se permite exclusivamente para preservar versiones legacy token-only.
    -- Una versión activa para nuevos pagos debe cumplir los secretos exigidos por el proveedor.
    webhook_secret_enc TEXT NULL,
    account_id VARCHAR(120) NULL,
    account_label VARCHAR(190) NULL,
    created_by VARCHAR(120) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_payment_gateway_credentials_provider (provider, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS payment_gateway_config (
    provider VARCHAR(40) NOT NULL,
    configured TINYINT(1) NOT NULL DEFAULT 0,
    active TINYINT(1) NOT NULL DEFAULT 0,
    current_credential_id BIGINT UNSIGNED NULL,
    updated_by VARCHAR(120) NULL,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (provider),
    CONSTRAINT fk_payment_gateway_config_credential
      FOREIGN KEY (current_credential_id) REFERENCES payment_gateway_credentials(id)
      ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Ejemplo conceptual para la tabla de dominio. NO ejecutar literalmente si el proyecto
-- no tiene una tabla `orders` o si la migración requiere otro nombre/posición.
--
-- ALTER TABLE orders
--   ADD COLUMN payment_credential_id BIGINT UNSIGNED NULL,
--   ADD KEY idx_orders_payment_credential (payment_credential_id),
--   ADD CONSTRAINT fk_orders_payment_credential
--     FOREIGN KEY (payment_credential_id) REFERENCES payment_gateway_credentials(id)
--     ON UPDATE CASCADE ON DELETE RESTRICT;
--
-- La aplicación debe ligar la operación local a payment_credential_id antes de crear
-- el recurso externo y debe serializar checkout/rotación mediante locks de configuración.
