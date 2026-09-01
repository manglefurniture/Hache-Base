# Tests

Suite base para proyectos construidos sobre Hache-Base.

## Incluido

- `static/php-syntax.sh`: sintaxis PHP.
- `static/ProductionReadinessDocsTest.php`: paridad 126/126 entre el registro canónico del Standard y la Checklist.
- `audit/`: pruebas del módulo de auditoría.
- `common/`: utilidades reutilizables, incluyendo estados temporales, zona horaria y contrato de estados asíncronos P0-05.
- `fixtures/async-operations/scenarios.json`: escenarios offline para aceptación, confirmación, timeout ambiguo, retry seguro y reconciliación.
- `ui/`: regresiones de tokens, temas, contraste de fallbacks, presets, estados, responsive/container queries, reduced motion, peso y comportamiento JS; incluye compatibilidad del relieve de backend.
- `security/ProductionReadinessCoreTest.php`: contrato de errores HTTP, request/correlation IDs y redacción/log schema mínimo.
- `security/HeadersTest.php`: contrato P0-07 de headers baseline, HSTS opt-in, CSP report-only/enforce y proxy HTTPS confiable.
- `security/SessionSecurityTest.php`: contrato P0-08 de cookies, trusted HTTPS, fixation, expiración, elevación y logout.
- `deployment/HealthCheckTest.sh`: regresiones offline de liveness/readiness/smoke, incluido body/version incorrecto.
- `deployment/DeployRunnerTest.sh`: regresión P0-10 con fases, fallo parcial, record persistente, smoke, ventana, rollback explícito y manual recovery.
- `smoke/http-smoke.sh`: smoke HTTP configurable y separado de liveness/readiness.
- `integration/`: contratos e integraciones reutilizables; incluye mailer HTTPS, HMAC de webhooks, cifrado/versionado de credenciales y persistencia P0-06 inbox/outbox/idempotency.
- `run.sh`: punto de entrada común para pruebas que no requieren MariaDB persistente del workflow.

## Ejecución

```bash
bash tests/run.sh
```

Si se define `SMOKE_BASE_URL`, el runner ejecuta también el smoke HTTP contra el entorno indicado.

La regresión `tests/integration/InboxOutboxMariaDbTest.sh` se ejecuta desde CI después de cargar los schemas opcionales en MariaDB.

## Regla

Los Critical User Flows deben documentarse con `templates/CRITICAL-USER-FLOWS.md` y tener comprobación automatizada o smoke reproducible antes de producción según el nivel aplicable. Las pruebas con escritura no deben contaminar datos históricos reales.

Cada proyecto añade casos específicos de permisos, sedes, pagos y reglas de negocio sobre fixtures/staging.

Las pruebas base de integraciones no hacen llamadas reales a proveedores ni necesitan secretos. Cada proyecto debe añadir smoke/integration tests contra sandbox/staging cuando el proveedor lo permita y una prueba operativa controlada desde el host real antes de producción.

Los patrones UI reutilizables deben probar sus tokens y estados críticos, pero cada proyecto derivado debe añadir regresiones para controles dinámicos, excepciones planas y clases locales que adopte.

## Errores, logs y correlación

El Core prueba offline códigos canónicos, `request_id`/`correlation_id`, payloads y redacción de logs. Los proyectos siguen siendo responsables de probar sus códigos de dominio, rutas reales y eventos operativos.

## Security headers P0-07

`tests/security/HeadersTest.php` demuestra que:

- el baseline no inventa CSP ni activa HSTS sin aprobación del proyecto;
- al activar HSTS, `includeSubDomains` y `preload` siguen apagados por default;
- `preload` exige HSTS, `includeSubDomains` y `max-age` mínimo de un año;
- `max_age=0` puede expresarse para retiro/rollback cuando corresponda;
- CSP puede permanecer `off`, pasar a `report-only` y solo llegar a `enforce` por configuración explícita;
- la composición CSP rechaza directivas/valores inseguros;
- `X-Forwarded-Proto` de un cliente o IP no confiable no convierte HTTP en HTTPS;
- un proxy confiable debe entregar un único valor de esquema.

La prueba offline no sustituye evidencia SEC-001/002/003 del entorno real.

## Session security P0-08

`tests/security/SessionSecurityTest.php` usa una sesión PHP real aislada en un directorio temporal y demuestra:

- cookie `Secure` sobre HTTPS efectivo, `HttpOnly`, SameSite y scope configurables;
- `SameSite=None` se rechaza sobre HTTP;
- forwarded proto spoofeado/no confiable/multi-hop no activa `Secure`;
- proxy exacto confiable sí permite reconocer HTTPS terminado upstream;
- `session.use_strict_mode=1`, `session.use_only_cookies=1` y `session.use_trans_sid=0`;
- `Auth::login()` cambia el session ID antes de establecer el usuario;
- `Auth::elevate()` exige sesión autenticada, no puede cambiar de principal y vuelve a rotar el ID;
- idle timeout y absolute timeout expiran exactamente en el límite, eliminan auth y rotan el ID;
- logout destruye la sesión servidor, limpia estado e invalida el ID local.

Esto valida la primitive. SEC-007 sigue requiriendo evidencia HTTP del proyecto desplegado: cookie real, login, rutas protegidas, elevación, expiración, logout y configuración del proxy mediante `templates/SESSION-SECURITY.md`.

## Deploy/recovery P0-10

`tests/deployment/DeployRunnerTest.sh` crea repositorios Git temporales y prueba el runner sin tocar infraestructura real. Demuestra:

- orden de estados `started`, `code_changed`, `migrations_applied`, `tests_passed`, `healthy`;
- `migrations_applied status=not_applicable` cuando no hay comando de migración;
- readiness y smoke antes y después de una ventana de observación;
- fallo en tests con `state=failed`, `failed_phase` y exit code conservado;
- ausencia de rollback automático inseguro tras un fallo parcial;
- `rollback.sh` puede anexar `state=rolled_back` al mismo record;
- `mark-deploy-recovery.sh` puede cerrar evidencia con `manual_recovery`;
- `REQUIRE_SMOKE=1` sin contrato configurado falla antes de cambiar código.

La regresión valida el contrato del runner. No demuestra que un proyecto haya probado staging, compatibilidad de migraciones, restore, señales reales ni su CUF desplegado; esa evidencia se documenta con `templates/DEPLOY-RECOVERY.md`.

## Estados asíncronos P0-05

`tests/common/AsyncOperationStateTest.php` valida aceptación, confirmación, ambigüedad, retry seguro, reconciliación y terminalidad.

## Persistencia P0-06

`tests/integration/AsyncPersistenceContractTest.php` y `InboxOutboxMariaDbTest.sh` cubren vocabulario persistido, duplicados, concurrencia, ambigüedad, out-of-order, reprocess y claims.

## Liveness, readiness y smoke

`tests/deployment/HealthCheckTest.sh` no necesita red: reemplaza `curl` por un fixture controlado y demuestra que readiness falla ante body/version incorrectos.

El smoke real solo se ejecuta cuando se configura `SMOKE_BASE_URL`; debe apuntar a una URL/entorno controlado.

## Reglas temporales

Toda regla cuyo resultado cambie por fecha debe probar, como mínimo, día anterior/inicio/final/posterior y zona horaria operativa correcta.

## Consistencia e idempotencia

Cuando varias superficies muestran el mismo estado de negocio, incluir una regresión que demuestre que parten de la misma definición canónica. Si existe una reconciliación persistida, probar que puede ejecutarse repetidamente sin producir resultados contradictorios ni escrituras fuera de su contexto autorizado.

Para webhooks/jobs repetibles y efectos secundarios, probar duplicados, fuera de orden y no duplicación/reversión de la mutación central.
