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

## HTTPS detrás de proxy — P0-07

`security/headers.php` no acepta automáticamente `X-Forwarded-Proto` como prueba de HTTPS. Si TLS termina en un proxy/load balancer antes de PHP, el proyecto debe declarar IPs exactas de proxy confiable en la configuración de `Headers` y demostrar que ese proxy sobrescribe/normaliza el esquema a un único `https` o `http`.

Un valor multi-hop separado por comas se rechaza por ambigüedad. La IP se compara contra `REMOTE_ADDR`; este helper mínimo no interpreta CIDR.

La decisión de confianza documentada aquí **solo** habilita detección HTTPS para HSTS P0-07. No se usa como autoridad para IP de cliente, sesión, cookies, auth o auditoría. Esos aspectos quedan fuera de P0-07 y pertenecen a P0-08.

Antes de activar HSTS o promover CSP a enforcement, completar `templates/SECURITY-HEADERS.md` y probar headers/CUF en staging y en el entorno real.

## Requisitos por proyecto

Configurar en el entorno real `APP_ROOT`, `BACKUP_ROOT`, conexión de base, `HEALTHCHECK_URL`, `TARGET_COMMIT` y, cuando aplique, `MIGRATION_COMMAND`/`TEST_COMMAND`.

Para nuevos proyectos configurar además un marcador de readiness mediante `EXPECTED_HEALTH_BODY` o `EXPECTED_HEALTH_VERSION` y documentarlo en `templates/CRITICAL-USER-FLOWS.md`.

Probar el runner primero en staging antes de habilitar CI/CD hacia producción.
