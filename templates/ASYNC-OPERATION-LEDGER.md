# Async Operation / Event Ledger — plantilla

Plantilla opt-in para proyectos con proveedores, jobs, webhooks o efectos externos cuyo resultado final puede ocurrir después de que la aplicación haya aceptado o iniciado la operación.

**No es un schema SQL universal.** Antes de persistir este modelo, adaptar tipos, índices, retención, PII, particionamiento y constraints al proyecto real mediante migraciones nuevas.

## 1. Operación

Una fila lógica por efecto de negocio externo que debe poder seguirse hasta resultado autoritativo.

| Campo | Propósito |
| --- | --- |
| `operation_id` | ID local estable y no sensible. |
| `operation_type` | Tipo estable, por ejemplo `transactional_email`, `payment_capture`, `webhook_delivery`, `background_job`. |
| `business_reference` | Referencia mínima no sensible al recurso/CUF; usar hash/ID interno cuando convenga. |
| `provider` | Proveedor/adaptador responsable, si aplica. |
| `provider_operation_id` | ID externo cuando exista; no confundirlo con confirmación de éxito. |
| `status` | Uno de los estados del contrato `AsyncOperationState`. |
| `attempt_count` | Número de intentos iniciados. |
| `request_id` | Request ID del intento/creación más reciente relevante. |
| `correlation_id` | Correlación estable del CUF/operación. |
| `last_error_code` | Código seguro y estable; no guardar secretos. |
| `next_retry_at` | Próximo retry solo cuando `status=retry_pending`. |
| `last_reconciled_at` | Última consulta/evento autoritativo de reconciliación. |
| `created_at` / `updated_at` | Timestamps UTC. |

## 2. Eventos

Append-only recomendado para reconstruir qué se observó y por qué cambió el estado.

| Campo | Propósito |
| --- | --- |
| `event_id` | ID local único. |
| `operation_id` | Operación relacionada. |
| `event_type` | Nombre estable del evento observado. |
| `state_before` / `state_after` | Transición validada por el contrato. |
| `source` | `application`, `provider_response`, `provider_event`, `reconciler`, `retry_worker`, etc. |
| `provider_event_id` | ID externo para dedupe cuando el proveedor lo ofrezca. |
| `request_id` / `correlation_id` | Trazabilidad con logs y CUF. |
| `occurred_at` | Momento declarado por la fuente, si es confiable. |
| `observed_at` | Momento UTC en que la aplicación observó el evento. |
| `details` | Solo metadata mínima/redactada; nunca tokens, passwords, cookies, CVV, tarjetas completas ni payloads sensibles completos. |

## 3. Reglas

1. `accepted` **no equivale** a `confirmed`.
2. `outcome_unknown` no autoriza retry ciego: primero reconciliar o recibir evidencia autoritativa.
3. `retry_pending` solo se usa cuando el proyecto sabe que reintentar es seguro según su contrato/idempotencia.
4. `confirmed`, `failed_final` y `cancelled` son terminales en el contrato base; cualquier reversión/corrección posterior debe modelarse como operación o evento de dominio explícito, no reescribiendo historia silenciosamente.
5. Cada intento nuevo conserva el mismo `correlation_id` de negocio y obtiene un `request_id` nuevo cuando cruza una nueva frontera de ejecución.
6. El ledger operativo no sustituye el audit log ni el historial financiero autoritativo.
7. No adoptar persistencia universal en Hache Base hasta tener un caso real y migración específica. P0-06 cubre inbox/outbox/idempotency claim y sigue siendo separado.

## 4. Checklist de adopción

- [ ] Definido qué evidencia constituye `confirmed` y `failed_final` para este proveedor/CUF.
- [ ] Identificados timeouts/errores que producen `outcome_unknown`.
- [ ] Retry condicionado a idempotencia o prueba de no aplicación.
- [ ] Reconciliación tiene endpoint/evento/fuente autoritativa.
- [ ] `provider_operation_id` y `provider_event_id` se guardan solo si son no secretos.
- [ ] Retención y PII revisadas.
- [ ] Tests cubren aceptación sin confirmación, timeout ambiguo, retry seguro y reconciliación.
