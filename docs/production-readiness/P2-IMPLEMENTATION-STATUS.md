# Production Readiness P2 — estado de implementación

> P2 aumenta madurez operativa y no bloquea por sí solo la mayoría de releases. Este documento sigue `PRODUCTION-READINESS-ROADMAP.md` y no modifica el Standard ni la Checklist.

## Corte

- Inicio autorizado: 2026-09-06.
- Base inicial P2: `948fe6fc0cb7db9f58c20c306d1d091f7531bb15`.
- P0: cerrado en Hache Base.
- P1: cerrado en Hache Base con criterio de salida validado por el piloto real Nivel C Hache Natación.
- P2 se implementa incrementalmente; una primitive/Extension disponible no se activa globalmente ni equivale a evidencia de proyecto.

## Estado

| Ítem | Estado | Alcance en Hache Base |
| --- | --- | --- |
| P2-01 | IMPLEMENTADO / MERGEADO | Extension opt-in y vendor-neutral para logs, métricas y trazas; exporter contract, trace context estricto, minimización, fail-open y plantilla de adopción. PR #40, merge `ca7e243f3661f40accf9d1f762e5897b4419cd80`; follow-up automático de ciclo de vida/contexto cerrado en PR #42, merge `0b57b4873e67bfe95284b63713fb6d92f799a8d0`. |
| P2-02 | IMPLEMENTADO / MERGEADO | Política machine-readable de alertas sobre golden signals/CUF, validator determinista, plantilla de runbooks, control de ruido y regresión offline. PR #41, merge `a3398bf0fc7851beb04ea46214def65ce458f236`. |
| P2-03 | IMPLEMENTADO EN ESTE PAQUETE | Failure fixtures deterministas y solo de test para timeout/429/5xx/DNS/storage, sin retry implícito ni fault injection en producción; plantilla de adopción y regresión integrada a la suite. |
| P2-04 | NO INICIADO | Upload Extension segura; requiere caso real y threat model antes de promover runtime reusable. |
| P2-05 | NO INICIADO | Rate limit shared-store; requiere Redis/DB/edge real antes de elegir implementación. |
| P2-06 | NO INICIADO | SBOM/provenance y pinning de actions/containers para Nivel C. |
| P2-07 | NO INICIADO | Restore drills programados e historial por proyecto C; la agenda/evidencia pertenece al proyecto. |

## P2-01 — observabilidad neutral

Se implementó la alternativa **adaptadores neutrales** contemplada por el roadmap, no una plataforma APM obligatoria.

Incluye `TelemetryExporter`, `TraceContext`, `ObservabilityBridge`, plantilla de adopción y regresión offline. No instala SDK/collector/provider, no activa telemetría global y no cambia el estado de controles `OBS-*`.

El follow-up del PR #42 endureció el contrato para runtimes persistentes: `RequestContext` debe ser explícito por record o inyectarse como `boundaryContext` scoped a un único request/job; además `measure()` valida el nombre del span antes de ejecutar callbacks con posibles efectos laterales.

## P2-02 — alertas accionables y runbooks

P2-02 materializa el requisito del roadmap y de `OBS-006` sin imponer umbrales universales ni un proveedor de alertas.

Incluye:

- `templates/ALERTING-RUNBOOKS.md` — contrato de adopción por CUF/integración, golden signals, severidad, routing, control de ruido, runbook mínimo y evidencia;
- `templates/alert-policy.example.json` — política machine-readable con ejemplos ficticios;
- `tools/observability/validate-alert-policy.mjs` — valida estructura y exige por alerta ID/CUF/signal/métrica/condición/threshold/ventana/persistencia/severidad/owner/runbook/acción/data source;
- `tests/observability/AlertPolicyTest.mjs` — regresión offline de casos válidos e inválidos;
- integración del test en `tests/run.sh`.

Signals soportadas por el contrato:

- `latency`, `traffic`, `errors`, `saturation`;
- `cuf_success`, `cuf_failure`, `cuf_pending`.

El validator **no decide** si un threshold es correcto para el negocio, si el canal de routing funciona o si el runbook resuelve un incidente real. Esas decisiones/evidencias pertenecen al proyecto.

## Criterio de terminado P2-02 en Base

P2-02 se considera cubierto como contrato reusable cuando:

1. ninguna alerta puede declararse sin threshold, ventana, owner, acción y runbook;
2. las señales del contrato cubren golden signals y resultado/pendientes por CUF;
3. los thresholds permanecen project-owned y deben justificar baseline/revisión;
4. la plantilla exige prueba positiva, negativa/control de ruido y routing real;
5. el runbook exige confirmación, acciones seguras, correlación, recovery, escalación y criterio de cierre;
6. existe una regresión offline que bloquea políticas incompletas o ambiguas.

La existencia de estas plantillas/tests no marca `OBS-006` ni otro control como PASS en un proyecto derivado.

## P2-03 — failure fixtures

P2-03 implementa la frontera reusable de pruebas de fallo sin introducir chaos tooling ni dependencias de infraestructura.

Incluye:

- `tests/fixtures/failures/FailureFixture.php` — harness determinista y solo de test;
- categorías estables para `timeout`, `http_429`, `http_5xx`, `dns` y `storage`;
- metadata de fase, status HTTP y `Retry-After` cuando aplica;
- scripts de fallo repetible para probar fallo→éxito y límites de intentos sin `sleep`, red, DNS o storage real;
- `tests/resilience/FailureFixtureContractTest.php` — regresión de las cinco familias, metadata, secuencias y entradas inválidas;
- `templates/FAILURE-RESILIENCE.md` — matriz de adopción por CUF/adapter, timeout, retry, idempotencia, reconciliación, observabilidad y evidencia;
- integración del contrato a `tests/run.sh`.

La fixture **describe el fallo, no la decisión de negocio**. No expone `should_retry`, estado final ni política universal: cada proyecto/adaptador debe decidir retry/reconcile/final failure según idempotencia, outcome autoritativo, límites y semántica del proveedor.

## Criterio de terminado P2-03 en Base

P2-03 se considera cubierto como primitive/fixture reusable cuando:

1. existen escenarios reproducibles para las cinco familias exigidas por el roadmap;
2. los fixtures no realizan fault injection en producción ni dependen de servicios externos;
3. `429` conserva `Retry-After` como evidencia, pero no autoriza retry por sí mismo;
4. `5xx`, timeout, DNS y storage no implican automáticamente éxito, retry o estado final;
5. el harness permite secuencias deterministas de fallo y recuperación para que un proyecto pruebe límites e idempotencia;
6. la plantilla exige evidencia real del adapter/CUF antes de declarar resiliencia PASS;
7. la suite de Hache Base ejecuta la regresión de contrato.

La existencia de los fixtures no marca controles `ROB-*` ni un proyecto derivado como PASS.

## Siguiente frontera

Después de merge y CI verde de P2-03, **no se debe saltar automáticamente a P2-04/P2-05**: ambos requieren un caso real que justifique upload/storage o shared-state rate limiting. El siguiente movimiento debe ser auditar qué ítem P2 tiene dependencias reales ya disponibles; P2-06 puede evaluarse sin inventar infraestructura, mientras P2-07 requiere agenda/evidencia por proyecto C.
