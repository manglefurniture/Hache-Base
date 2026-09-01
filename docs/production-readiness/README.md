# Production Readiness — Hache Base

Paquete normativo y Core mínimo para demostrar cuándo un proyecto derivado puede considerarse preparado para producción.

## Fuente normativa

`PRODUCTION-READINESS-STANDARD.md` v1.1 es la **única fuente normativa**.

Los demás documentos no crean requisitos nuevos:

- `PRODUCTION-READINESS-CHECKLIST.md` — proyección verificable del registro canónico de controles.
- `PRODUCTION-READINESS-AUDIT.md` — fotografía de Hache Base antes de esta primera implementación; conserva valor histórico para explicar los huecos detectados.
- `PRODUCTION-READINESS-ROADMAP.md` — secuencia de implementación P0/P1/P2/P3.
- `PRODUCTION-READINESS-NORMALIZATION-REPORT.md` — evidencia histórica de la normalización 126/126 Standard ↔ Checklist; no sustituye la norma.
- `RESEARCH-SOURCES.md` — fuentes primarias y referencias técnicas.
- `ASYNC-OPERATIONS.md` — contrato reusable implementado en P0-05 para distinguir aceptación, confirmación, ambigüedad, retry y reconciliación.

Si una síntesis contradice el registro canónico de la sección 24 del Standard, **prevalece el Standard**.

## Primera fase implementada

Esta fase se limitó deliberadamente a:

- **P0-01** — paquete documental normalizado enlazado desde README/catálogo.
- **P0-02** — `templates/CRITICAL-USER-FLOWS.md`.
- **P0-03** — contrato Core de errores HTTP comunes, códigos internos estables y `request_id` sin retirar las APIs existentes de `ApiResponse`.
- **P0-04** — `RequestContext` y logging estructurado mínimo con correlación y redacción de secretos.
- **P0-09** — separación conceptual/operativa de liveness, readiness y smoke; readiness puede validar body/version y usa temporales seguros por ejecución.

## Segunda fase incremental implementada — P0-05

P0-05 añade, sin modificar proveedores ni persistencia real:

- `src/common/AsyncOperationState.php` — vocabulario y transiciones base para operaciones asíncronas/externas;
- `docs/production-readiness/ASYNC-OPERATIONS.md` — semántica de `accepted != confirmed`, ambigüedad, retry y reconciliación;
- `templates/ASYNC-OPERATION-LEDGER.md` — plantilla conceptual de operation/event ledger, sin schema SQL universal;
- `tests/fixtures/async-operations/scenarios.json` + `tests/common/AsyncOperationStateTest.php` — fixtures offline que ejercitan aceptación, confirmación, timeout ambiguo, retry seguro y reconciliación.

P0-05 **no** integra todavía el contrato dentro de `ResendMailer`, pagos, n8n ni otros módulos reales. Tampoco añade tablas, migraciones, colas, Redis, workers ni inbox/outbox. Esas decisiones permanecen opt-in y P0-06 sigue separado.

No se implementan todavía P0-06/P0-07/P0-08/P0-10/P0-11/P0-12 ni P1+.

## Uso en un proyecto derivado

1. Clasificar el proyecto A/B/C según el Standard.
2. Completar `templates/CRITICAL-USER-FLOWS.md` para sus CUF reales.
3. Evaluar la Checklist solo con evidencia del proyecto/entorno real.
4. Adoptar las primitives Core que apliquen; no copiar Extensions innecesarias.
5. Si existe una operación asíncrona/externa crítica, definir qué evidencia significa `accepted`, `confirmed`, `failed_final` y cuándo un retry es seguro antes de persistir un ledger.
6. Mantener `NOT EVALUATED` mientras no exista evidencia suficiente. `N/A` exige justificación verificable.

## Contratos Core implementados

### Errores y request ID

`security/api-response.php` conserva `json()`, `success()` y `error()` y añade:

- códigos canónicos para 400/401/403/404/409/422/429/500/503;
- `errorForStatus()` para errores de plataforma;
- `request_id` en el envelope y headers `X-Request-Id`/`X-Correlation-Id`;
- helpers de payload que permiten pruebas sin enviar/terminar el proceso.

Los códigos de dominio propios siguen siendo responsabilidad del proyecto y deben permanecer estables una vez publicados.

### Correlación y logs

- `src/common/RequestContext.php` genera o normaliza `request_id` y `correlation_id`, limitando identificadores externos antes de propagarlos.
- `src/common/StructuredLogger.php` emite una línea JSON con timestamp UTC, severity, environment, service/version, event, request/correlation IDs y contexto redactado.

El logger es una primitive, no una plataforma APM. OpenTelemetry, error trackers y alerting avanzado siguen siendo Extensions.

### Estados asíncronos y reconciliación

`src/common/AsyncOperationState.php` define estados neutrales para distinguir intención local, aceptación externa, resultado ambiguo, retry seguro, reconciliación y resultado autoritativo. `confirmed` es el único éxito autoritativo del contrato base; `accepted` nunca se interpreta automáticamente como éxito final.

El ledger de `templates/ASYNC-OPERATION-LEDGER.md` es una plantilla opt-in. No sustituye audit logs, historial financiero, idempotency claims ni schemas específicos del proyecto.

### Liveness, readiness y smoke

- `deployment/liveness-check.sh` confirma que el proceso/endpoint responde con el status esperado.
- `deployment/health-check.sh` actúa como gate de **readiness** compatible con el nombre histórico; valida status y, cuando se configura, body exacto y/o `version` JSON.
- `tests/smoke/http-smoke.sh` comprueba una ruta desplegada configurable; un proyecto B/C debe apuntarlo a un CUF/control funcional representativo, no confundirlo con liveness.

Para nuevos proyectos se recomienda configurar `EXPECTED_HEALTH_BODY` o `EXPECTED_HEALTH_VERSION`. `HEALTHCHECK_ALLOW_STATUS_ONLY=1` existe únicamente como compatibilidad gradual para consumidores antiguos; puede fijarse a `0` para exigir contrato de contenido.

## Regla de promoción

Una primitive no se considera cumplimiento automático de un proyecto derivado. El proyecto debe aportar la evidencia exigida por su nivel/CUF y por la Checklist.
