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
| P2-01 | IMPLEMENTADO / MERGEADO | Extension opt-in y vendor-neutral para logs, métricas y trazas; exporter contract, trace context estricto, minimización, fail-open y plantilla de adopción. PR #40, merge `ca7e243f3661f40accf9d1f762e5897b4419cd80`. |
| P2-02 | IMPLEMENTADO EN ESTE PAQUETE | Política machine-readable de alertas sobre golden signals/CUF, validator determinista, plantilla de runbooks, control de ruido y regresión offline. |
| P2-03 | NO INICIADO | Failure fixtures timeout/429/5xx/DNS/storage. |
| P2-04 | NO INICIADO | Upload Extension segura; requiere caso real y threat model antes de promover runtime reusable. |
| P2-05 | NO INICIADO | Rate limit shared-store; requiere Redis/DB/edge real antes de elegir implementación. |
| P2-06 | NO INICIADO | SBOM/provenance y pinning de actions/containers para Nivel C. |
| P2-07 | NO INICIADO | Restore drills programados e historial por proyecto C; la agenda/evidencia pertenece al proyecto. |

## P2-01 — observabilidad neutral

Se implementó la alternativa **adaptadores neutrales** contemplada por el roadmap, no una plataforma APM obligatoria.

Incluye `TelemetryExporter`, `TraceContext`, `ObservabilityBridge`, plantilla de adopción y regresión offline. No instala SDK/collector/provider, no activa telemetría global y no cambia el estado de controles `OBS-*`.

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

## Siguiente frontera

Después de merge y CI verde de P2-02, el siguiente ítem secuencial es **P2-03** (failure fixtures). P2-04/P2-05 siguen bloqueados a un caso real que justifique storage/shared state.
