# Deployment

Hache-Base adopta un despliegue verificable, observable y recuperable. El runner es una plantilla Core: no convierte por sí solo a un proyecto en Production Ready ni decide automáticamente un rollback de DB.

## Scripts

- `preflight.sh`: requisitos, repo limpio y capacidad de backup.
- `backup.sh`: commit + dump MariaDB + snapshot local de entorno protegido.
- `deploy.sh`: commit fijado, rollback ref, backup, migraciones configurables, pruebas, readiness, smoke y ventana de observación P0-10.
- `liveness-check.sh`: confirma que el proceso/endpoint responde; no afirma que el servicio esté listo para tráfico.
- `health-check.sh`: nombre compatible del gate de **readiness**; valida status y puede exigir body/version.
- `rollback.sh`: reversión explícita de código; registra un evento `code_rollback` con `recovery_state=pending_verification` sin convertir un fallo de logging en fallo del rollback ya ejecutado.
- `mark-deploy-recovery.sh`: registra explícitamente `manual_recovery` o `rolled_back` solo después de la recuperación y sus verificaciones correspondientes.
- `DEPLOY-FAILURE-RUNBOOK.md`: respuesta mínima ante fallo parcial.
- `BACKUP-ROLLBACK.md`: política y límites de recuperación.

El smoke funcional vive en `tests/smoke/http-smoke.sh` para mantener separado el recorrido desplegado de liveness/readiness.

## Flujo P0-10

Flujo operativo base:

`PREFLIGHT -> ROLLBACK_REF -> BACKUP -> TARGET_COMMIT -> MIGRATIONS -> TESTS -> READINESS -> SMOKE -> OBSERVATION -> HEALTHY`

El registro persistente usa estados canónicos según aplicabilidad:

- `started`
- `code_changed`
- `migrations_applied` (`status=not_applicable` cuando no existe migración en esa ejecución)
- `tests_passed`
- `healthy`
- `failed`
- `rolled_back` o `manual_recovery` después de una recuperación explícita

Las líneas `DEPLOY_STATE` registran fases/resultados del deploy. Las líneas `DEPLOY_GATE` conservan evidencia de readiness, smoke y observación, incluido `status=not_evaluated` cuando un gate compatible no está configurado.

`deploy.sh` crea `DEPLOY_RECORD_FILE` bajo `DEPLOY_RECORD_ROOT` (por default `$BACKUP_ROOT/deploy-records`) con `umask 077`, directorio 700 y archivo 600. `DEPLOY_RECORD_ROOT` se resuelve físicamente y **debe quedar fuera de `APP_ROOT`**; si apunta al working tree directa o indirectamente mediante symlink, el runner falla antes de cambiar código.

El runner se detiene ante errores. El trap emite `DEPLOY_RECOVERY_REQUIRED` con `failed_phase`, exit code, runbook, record y rollback ref disponibles. Preflight, creación del record, rollback ref, backup y cambio de código tienen fases diferenciadas, además de migraciones/tests/gates. **No ejecuta automáticamente un rollback de base de datos ni un rollback ciego de código**: después de migraciones una reversión automática puede dejar esquema/código incompatibles.

Completar `templates/DEPLOY-RECOVERY.md` por proyecto para declarar la matriz código/DB/assets/config, punto de no retorno, smoke, ventana, señales y criterio exacto de rollback.

## Smoke post-release

El runner admite dos formas:

- `SMOKE_BASE_URL`: ejecuta `tests/smoke/http-smoke.sh` contra esa base.
- `SMOKE_COMMAND`: comando específico del proyecto cuando el CUF requiere otra comprobación.

`REQUIRE_SMOKE=1` hace que ausencia de ambos sea un error de configuración **antes de cambiar código**.

Por compatibilidad, el default es `REQUIRE_SMOKE=0`. Si no existe smoke configurado, el runner persiste `DEPLOY_GATE ... gate=smoke status=not_evaluated ... evidence=NOT_EVALUATED`; no lo transforma en PASS. Un proyecto solo puede marcar DPL-005 según la evidencia real y aplicabilidad del Standard.

## Ventana de observación

`OBSERVATION_SECONDS` controla una ventana mínima después del primer readiness/smoke. Si es mayor que cero, al finalizar la espera el runner vuelve a ejecutar readiness y smoke antes de registrar `healthy`.

`REQUIRE_OBSERVATION=1` exige una ventana mayor que cero antes de cambiar código. Por compatibilidad ambos defaults son `OBSERVATION_SECONDS=0` y `REQUIRE_OBSERVATION=0`; en ese caso el record conserva `DEPLOY_GATE ... gate=observation status=not_evaluated ... evidence=NOT_EVALUATED`.

La segunda comprobación es un gate mínimo. Error rate, logs, métricas de negocio e integridad continúan siendo responsabilidad del proyecto cuando su riesgo los requiera.

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

## HTTPS detrás de proxy — P0-07/P0-08

`security/request-security.php` centraliza la decisión de HTTPS usada por headers P0-07 y sesión P0-08. No acepta automáticamente `X-Forwarded-Proto`: si TLS termina en un proxy/load balancer antes de PHP, el proyecto debe declarar IPs exactas de proxy confiable y demostrar que ese proxy sobrescribe/normaliza el esquema a un único `https` o `http`.

Un valor multi-hop separado por comas se rechaza por ambigüedad. La IP se compara contra `REMOTE_ADDR`; este helper mínimo no interpreta CIDR ni deriva la IP real del cliente.

Antes de activar HSTS, promover CSP a enforcement o adoptar cookies `Secure` detrás de proxy, completar las plantillas P0-07/P0-08 y probar el entorno real.

## Recuperación explícita

`rollback.sh <commit-o-rama>` revierte solo código. Si se conoce el `DEPLOY_RECORD_FILE`, pasarlo en el entorno para anexar `DEPLOY_RECOVERY_EVENT event=code_rollback ... recovery_state=pending_verification`. Ese evento **no** cierra la recuperación ni equivale a `state=rolled_back`; confirma únicamente que el código volvió al ref solicitado. Si el append del record falla después del checkout, el script emite `ROLLBACK_RECORD_WARNING` pero conserva el éxito del rollback de código.

Después del rollback, ejecutar las verificaciones del runbook (readiness, smoke, commit efectivo, señales de integridad y ventana cuando aplique). Solo después de verificar la recuperación se registra el estado canónico final:

```bash
DEPLOY_RECORD_FILE=/ruta/record \
APP_ROOT=/ruta/app \
bash deployment/mark-deploy-recovery.sh rolled_back verificacion_post_rollback_ok
```

Cuando la recuperación fue manual:

```bash
DEPLOY_RECORD_FILE=/ruta/record \
APP_ROOT=/ruta/app \
bash deployment/mark-deploy-recovery.sh manual_recovery motivo_corto
```

El helper registra evidencia; no ejecuta la recuperación ni sustituye las verificaciones del runbook.

## Requisitos por proyecto

Configurar en el entorno real `APP_ROOT`, `BACKUP_ROOT`, conexión de base, `HEALTHCHECK_URL`, `TARGET_COMMIT` y, cuando aplique, `MIGRATION_COMMAND`/`TEST_COMMAND`.

`realpath` forma parte del preflight P0-10 porque la ubicación física del record debe verificarse antes de escribir evidencia.

Antes de declarar Production Ready, definir además:

- marcador de readiness (`EXPECTED_HEALTH_BODY` o `EXPECTED_HEALTH_VERSION`) cuando el stack lo permita;
- smoke aplicable y si debe exigirse con `REQUIRE_SMOKE=1`;
- `OBSERVATION_SECONDS` y `REQUIRE_OBSERVATION=1` cuando la ventana sea obligatoria;
- matriz y criterios en `templates/DEPLOY-RECOVERY.md`;
- staging drill de fallo y recuperación.

Probar el runner primero en staging antes de habilitar CI/CD hacia producción.
