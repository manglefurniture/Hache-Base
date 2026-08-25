-- OPTIONAL Hache-Base module for attendance-style recurring services.
-- Requires database/modules/core.sql concepts. Adapt before use.

CREATE TABLE IF NOT EXISTS attendance (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    organization_id BIGINT UNSIGNED NOT NULL,
    site_id BIGINT UNSIGNED NOT NULL,
    session_id BIGINT UNSIGNED NOT NULL,
    client_id BIGINT UNSIGNED NOT NULL,
    status VARCHAR(32) NOT NULL,
    recorded_by BIGINT UNSIGNED NULL,
    recorded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_attendance_session_client (session_id, client_id),
    INDEX idx_attendance_site (site_id),
    CONSTRAINT fk_attendance_organization FOREIGN KEY (organization_id) REFERENCES organizations(id),
    CONSTRAINT fk_attendance_site FOREIGN KEY (site_id) REFERENCES sites(id),
    CONSTRAINT fk_attendance_session FOREIGN KEY (session_id) REFERENCES service_sessions(id),
    CONSTRAINT fk_attendance_client FOREIGN KEY (client_id) REFERENCES clients(id),
    CONSTRAINT fk_attendance_user FOREIGN KEY (recorded_by) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS absences (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    organization_id BIGINT UNSIGNED NOT NULL,
    site_id BIGINT UNSIGNED NOT NULL,
    client_id BIGINT UNSIGNED NOT NULL,
    session_id BIGINT UNSIGNED NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'reported',
    reason VARCHAR(255) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_absence_session_client (session_id, client_id),
    CONSTRAINT fk_absences_organization FOREIGN KEY (organization_id) REFERENCES organizations(id),
    CONSTRAINT fk_absences_site FOREIGN KEY (site_id) REFERENCES sites(id),
    CONSTRAINT fk_absences_client FOREIGN KEY (client_id) REFERENCES clients(id),
    CONSTRAINT fk_absences_session FOREIGN KEY (session_id) REFERENCES service_sessions(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS replacement_sessions (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    organization_id BIGINT UNSIGNED NOT NULL,
    site_id BIGINT UNSIGNED NOT NULL,
    client_id BIGINT UNSIGNED NOT NULL,
    absence_id BIGINT UNSIGNED NULL,
    replacement_session_id BIGINT UNSIGNED NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'scheduled',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_replacements_client (client_id),
    CONSTRAINT fk_replacements_organization FOREIGN KEY (organization_id) REFERENCES organizations(id),
    CONSTRAINT fk_replacements_site FOREIGN KEY (site_id) REFERENCES sites(id),
    CONSTRAINT fk_replacements_client FOREIGN KEY (client_id) REFERENCES clients(id),
    CONSTRAINT fk_replacements_absence FOREIGN KEY (absence_id) REFERENCES absences(id),
    CONSTRAINT fk_replacements_session FOREIGN KEY (replacement_session_id) REFERENCES service_sessions(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
