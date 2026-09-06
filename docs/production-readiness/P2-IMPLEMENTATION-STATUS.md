# Production Readiness P2 — estado de implementación

> P2 aumenta madurez operativa y no bloquea por sí solo la mayoría de releases. Este documento sigue `PRODUCTION-READINESS-ROADMAP.md` y no modifica el Standard ni la Checklist.

## Corte

- Inicio autorizado: 2026-09-06.
- Base inicial: `948fe6fc0cb7db9f58c20c306d1d091f7531bb15`.
- P0: cerrado en Hache Base.
- P1: cerrado en Hache Base con criterio de salida validado por el piloto real Nivel C Hache Natación.
- P2 se implementa incrementalmente; una Extension disponible no se activa globalmente ni equivale a evidencia de proyecto.

## Estado

| Ítem | Estado | Alcance en Hache Base |
| --- | --- | --- |
| P2-01 | IMPLEMENTADO EN ESTE PAQUETE | Extension opt-in y vendor-neutral para logs, métricas y trazas; exporter contract, trace context estricto, minimización, fail-open y plantilla de adopción. |
| P2-02 | NO INICIADO | Plantillas de alertas sobre golden signals/CUF y runbooks. |
| P2-03 | NO INICIADO | Failure fixtures timeout/429/5xx/DNS/storage. |
| P2-04 | NO INICIADO | Upload Extension segura; requiere caso real y threat model antes de promover runtime reusable. |
| P2-05 | NO INICIADO | Rate limit shared-store; requiere Redis/DB/edge real antes de elegir implementación. |
| P2-06 | NO INICIADO | SBOM/provenance y pinning de actions/containers para Nivel C. |
| P2-07 | NO INICIADO | Restore drills programados e historial por proyecto C; la agenda/evidencia pertenece al proyecto. |

## P2-01 — decisión de diseño

Se implementa la alternativa **adaptadores neutrales** contemplada por el roadmap, no una plataforma APM obligatoria.

Incluye:

- `integrations/observability/TelemetryExporter.php` como única frontera hacia SDK/backend;
- `TraceContext.php` para `traceparent` W3C v00 estricto y spans hijos;
- `ObservabilityBridge.php` con envelopes de log/metric/span, request/correlation IDs, redacción y atributos privados bloqueados;
- exportación fail-open por default para no convertir una caída del APM en caída del CUF;
- `templates/OBSERVABILITY-ADOPTION.md` para owner, CUF, sampling, retención, coste, atributos, egress, fallback y evidencia;
- regresión offline sin red ni proveedor.

No incluye:

- SDK OpenTelemetry/Datadog/New Relic/Sentry u otro proveedor;
- collector/agent/sidecar;
- endpoint, API key o secret;
- sampling/retención globales;
- instrumentación automática de todos los módulos;
- baggage/tracestate;
- dashboards, alertas o SLO;
- cambio de estado automático de controles `OBS-*`.

## Criterio de terminado P2-01 en Base

P2-01 se considera cubierto como primitive reusable cuando:

1. logs/metrics/traces comparten envelope estable y correlación;
2. la propagación de trace context rechaza IDs inválidos;
3. el backend queda detrás de una interfaz vendor-neutral;
4. atributos sensibles conocidos se minimizan y el contrato prohíbe PII/payloads;
5. un fallo del exporter es fail-open por default y no reemplaza errores de negocio;
6. existe template de adopción con sampling/retención/coste/fallback;
7. la regresión offline ejecuta el contrato sin red.

El cumplimiento real de observabilidad sigue requiriendo evidencia del proyecto/entorno.

## Siguiente frontera

Después de merge y CI verde de P2-01, el siguiente ítem secuencial es **P2-02**. No se adelanta P2-04/P2-05 sin caso real que justifique storage/shared state.
