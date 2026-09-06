# Observability Adoption — plantilla P2-01

> Completar por proyecto antes de activar un exporter/APM. Esta plantilla no cambia el Standard ni convierte evidencia de Base en PASS.

## 1. Proyecto y owner

- Proyecto:
- Nivel A/B/C:
- Owner operativo:
- Fecha de revisión:
- Entorno(s):

## 2. CUF y objetivo

| CUF / operación | Pregunta operativa que debe responder la telemetría | Señal | Owner |
| --- | --- | --- | --- |
|  |  | log / metric / trace |  |

No instrumentar por aspiración. Cada señal debe ayudar a detectar, diagnosticar o medir un CUF/integración real.

## 3. Backend / exporter

- Exporter/adaptador:
- Backend/collector:
- Endpoint configurado fuera del código:
- Autenticación/secreto fuera del repo:
- Egress requerido:
- Timeout de exportación:
- Comportamiento si backend no responde:
- Procedimiento para desactivar:

## 4. Sampling, retención y coste

- Sampling traces:
- Sampling metrics/logs:
- Retención:
- Límite/coste esperado:
- Responsable de revisar crecimiento/cardinalidad:

## 5. Atributos permitidos

Lista cerrada de atributos que el proyecto autoriza.

| Atributo | Ejemplo | Cardinalidad esperada | Justificación |
| --- | --- | ---: | --- |
|  |  |  |  |

Prohibido por default: payload/body, email, teléfono, nombre, dirección, IDs de usuario/cliente/alumno, IP, user-agent, referrer, session ID, query string, URL completa, token/secreto y mensaje crudo de excepción.

## 6. Propagación

- `request_id` / `correlation_id` se mantienen entre:
- `traceparent` se propaga hacia:
- IDs externos aceptados solo después de validación/normalización:
- No se usa baggage/tracestate salvo justificación documentada:

## 7. Fallo de observabilidad

- Producción usa fail-open: sí / no (si no, justificar):
- Señal local de fallo del exporter:
- Runbook:
- Evidencia de que un fallo del APM no rompe el CUF:

## 8. Evidencia de adopción

- Tests unitarios/adaptador:
- Evidencia de entorno real:
- Timeline request → job/webhook/proveedor cuando aplique:
- Muestras verificadas sin PII/secrets:
- Revisión humana:

## 9. Estado

- `NOT EVALUATED` / `PARTIAL` / `PASS` / `N/A`:
- Justificación y enlaces:

La existencia de `integrations/observability/` nunca basta para marcar controles `OBS-*` como PASS.
