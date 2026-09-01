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
- `templates/ASYNC-OPERATION-LEDGER.md` — plantilla conceptual de operation/event ledger;
- `tests/fixtures/async-operations/scenarios.json` + `tests/common/AsyncOperationStateTest.php` — fixtures offline que ejercitan aceptación, confirmación, timeout ambiguo, retry seguro y reconciliación.

P0-05 no integra el contrato dentro de `ResendMailer`, pagos, n8n ni otros módulos reales.

## Tercera fase incremental implementada — P0-06

P0-06 añade una Extension **opt-in** de persistencia y claims; no la activa globalmente:

- `integrations/async/README.md` — contrato de inbox, outbox, idempotency claim, concurrencia, eventos fuera de orden y reprocess;
- `database/modules/async-inbox-outbox.sql` — schema plantilla para `integration_inbox`, `integration_outbox` e `integration_idempotency_claims`;
- `templates/INBOX-OUTBOX-IDEMPOTENCY.md` — plantilla de adopción por CUF/integración;
- `tests/integration/AsyncPersistenceContractTest.php` — evita drift entre el vocabulario persistido y `AsyncOperationState`;
- `tests/integration/InboxOutboxMariaDbTest.sh` — regresión MariaDB de duplicado, claim concurrente, ambigüedad, out-of-order y reprocess.

P0-06 **no** introduce Redis, broker, queue manager, worker universal, cron global ni integración automática con Resend/pagos/n8n. El proyecto que adopte la Extension debe crear su migración, worker/scheduler, retención, observabilidad y runbook según su riesgo.

No se implementan todavía P0-07/P0-08/P0-10/P0-11/P0-12 ni P1+.

## Uso en un proyecto derivado

1. Clasificar el proyecto A/B/C según el Standard.
2. Completar `templates/CRITICAL-USER-FLOWS.md` para sus CUF reales.
3. Evaluar la Checklist solo con evidencia del proyecto/entorno real.
4. Adoptar las primitives Core que apliquen; no copiar Extensions innecesarias.
5. Si existe una operación asíncrona/externa crítica, definir qué evidencia significa `accepted`, `confirmed`, `failed_final` y cuándo un retry es seguro.
6. Si el CUF necesita dedupe persistente, efectos posteriores al commit o reprocesamiento seguro, completar `templates/INBOX-OUTBOX-IDEMPOTENCY.md` antes de adoptar el schema P0-06.
7. Mantener `NOT EVALUATED` mientras no exista evidencia suficiente. `N/A` exige justificación verificable.

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

El ledger de `templates/ASYNC-OPERATION-LEDGER.md` sigue siendo conceptual. La persistencia P0-06 es opt-in y no sustituye audit logs ni historial financiero.

### Inbox/outbox/idempotency Extension

P0-06 conserva dos niveles separados:

- Core: semántica de estado de P0-05;
- Extension: persistencia/claims solo cuando un proyecto los necesita.

La inbox deduplica una recepción lógica; la outbox conserva una operación saliente e `idempotency_key` estable; el claim ligero cubre efectos que necesitan exclusión persistente sin una outbox completa.

Si `dispatch_started_at`/`effect_started_at` demuestra que la frontera externa pudo haberse cruzado y el resultado se perdió, no se permite retry ciego. La operación debe reconciliarse primero.

### Liveness, readiness y smoke

- `deployment/liveness-check.sh` confirma que el proceso/endpoint responde con el status esperado.
- `deployment/health-check.sh` actúa como gate de **readiness** compatible con el nombre histórico; valida status y, cuando se configura, body exacto y/o `version` JSON.
- `tests/smoke/http-smoke.sh` comprueba una ruta desplegada configurable; un proyecto B/C debe apuntarlo a un CUF/control funcional representativo, no confundirlo con liveness.

Para nuevos proyectos se recomienda configurar `EXPECTED_HEALTH_BODY` o `EXPECTED_HEALTH_VERSION`. `HEALTHCHECK_ALLOW_STATUS_ONLY=1` existe únicamente como compatibilidad gradual para consumidores antiguos; puede fijarse a `0` para exigir contrato de contenido.

## Regla de promoción

Una primitive o Extension disponible en Hache Base no se considera cumplimiento automático de un proyecto derivado. El proyecto debe aportar la evidencia exigida por su nivel/CUF y por la Checklist.
