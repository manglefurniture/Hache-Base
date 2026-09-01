# Deployment

Hache-Base adopta un despliegue verificable y reversible.

## Scripts

- `preflight.sh`: requisitos, repo limpio y capacidad de backup.
- `backup.sh`: commit + dump MariaDB + snapshot local de entorno protegido.
- `deploy.sh`: commit fijado, rollback ref, backup, migraciones configurables, pruebas y readiness gate.
- `liveness-check.sh`: confirma que el proceso/endpoint responde; no afirma que el servicio esté listo para tráfico.
- `health-check.sh`: nombre compatible del gate de **readiness**; valida status y puede exigir body/version.
- `rollback.sh`: reversión de código explícita.
- `BACKUP-ROLLBACK.md`: política y límites de recuperación.

El smoke funcional vive en `tests/smoke/http-smoke.sh` para mantener separado el recorrido desplegado de liveness/readiness.

## Flujo

`PREFLIGHT -> ROLLBACK_REF -> BACKUP -> TARGET_COMMIT -> MIGRATIONS -> TESTS -> READINESS -> DEPLOY_OK`

El runner se detiene ante errores. No ejecuta automáticamente un rollback de base de datos: después de migraciones, una reversión automática podría dejar esquema y código incompatibles.

## Liveness, readiness y smoke

### Liveness

Prueba mínima de que el proceso/endpoint responde con el status esperado.

Variables:

- `LIVENESS_URL` (o `HEALTHCHECK_URL` como fallback compatible).
- `EXPECTED_LIVENESS_STATUS` (default `200`).
- `LIVENESS_TIMEOUT`.

### Readiness

`health-check.sh` mantiene su nombre para no romper el runner existente, pero su contrato es readiness.

Variables:

- `HEALTHCHECK_URL` — obligatoria.
- `EXPECTED_HEALTH_STATUS` — default `200`.
- `EXPECTED_HEALTH_BODY` — body exacto opcional.
- `EXPECTED_HEALTH_VERSION` — si se configura, el body debe ser JSON y contener `version` coincidente.
- `HEALTHCHECK_TIMEOUT` — default `15`.
- `HEALTHCHECK_ALLOW_STATUS_ONLY` — default `1` por compatibilidad. En nuevos proyectos puede fijarse a `0` para exigir body/version.

El script usa un temporal único por ejecución y lo elimina al terminar. Un status 200 con body/version equivocado falla cuando existe contrato de contenido.

### Smoke funcional

`tests/smoke/http-smoke.sh` acepta:

- `SMOKE_BASE_URL` o URL como primer argumento.
- `SMOKE_PATH` (mantiene `HEALTH_PATH` como fallback compatible).
- `EXPECTED_SMOKE_STATUS`.
- `EXPECTED_SMOKE_BODY`.
- `SMOKE_TIMEOUT`.

Para B/C debe apuntar a una comprobación controlada del CUF principal o a una señal funcional equivalente; no usar un simple liveness como sustituto.

## Requisitos por proyecto

Configurar en el entorno real `APP_ROOT`, `BACKUP_ROOT`, conexión de base, `HEALTHCHECK_URL`, `TARGET_COMMIT` y, cuando aplique, `MIGRATION_COMMAND`/`TEST_COMMAND`.

Para nuevos proyectos configurar además un marcador de readiness mediante `EXPECTED_HEALTH_BODY` o `EXPECTED_HEALTH_VERSION` y documentarlo en `templates/CRITICAL-USER-FLOWS.md`.

Probar el runner primero en staging antes de habilitar CI/CD hacia producción.
