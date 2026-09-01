# Plantilla de adopción — Inbox / Outbox / Idempotency Claim

Usar esta plantilla únicamente si el proyecto necesita P0-06. Si el CUF no tiene callbacks repetibles, efectos posteriores al commit ni riesgo real de duplicación, marcar la Extension como no adoptada y justificarlo.

## 1. Identidad

- Proyecto:
- CUF:
- Integración:
- Dirección: inbound / outbound / ambas
- Responsable:
- Nivel A/B/C:
- Fecha:

## 2. Evento/operación lógica

- Nombre estable:
- Agregado/recurso afectado:
- Fuente autoritativa:
- Qué significa `accepted`:
- Qué significa `confirmed`:
- Qué evidencia permite `retry_pending`:
- Estados terminales:
- Política para `outcome_unknown`:

## 3. Dedupe inbound

- `source`:
- `external_event_id` o clave determinista:
- Restricción `UNIQUE`:
- ¿La firma/autenticidad se valida antes de mutar?:
- ¿Se consulta recurso autoritativo?:
- Política de duplicado:
- Política de evento fuera de orden:
- Secuencia/version fiable disponible:
- Retención inbox:

## 4. Outbox outbound

- Evento de negocio que crea la outbox:
- ¿Se persiste en la misma transacción que la mutación central?:
- Fórmula de `idempotency_key`:
- ¿Proveedor soporta idempotency key?:
- Payload mínimo:
- Datos sensibles/PII:
- Retención:
- `available_at`/backoff:
- Máximo de intentos:
- Política de `dispatch_started_at`:
- Política para claim huérfano:
- Reconciliación:
- Estado final esperado:

## 5. Claim ligero (si no hay outbox)

- `scope_name`:
- `claim_key`:
- Motivo para no usar outbox:
- Momento de `effect_started_at`:
- Cuándo puede liberarse/reintentarse:
- Qué ocurre ante timeout ambiguo:

## 6. Concurrencia

- Operación atómica usada para reclamar:
- Restricción `UNIQUE`:
- Locks/transacciones:
- Cómo se comprueba que solo un worker ganó:
- Riesgo de dos workers:
- Recuperación tras caída del worker:

## 7. Reprocess

- Quién puede solicitarlo:
- Evidencia requerida:
- ¿Reutiliza la misma fila?:
- ¿Reutiliza la misma `idempotency_key`?:
- Auditoría del motivo:
- ¿Puede reabrir `failed_final`?: no por defecto; documentar una nueva operación lógica si el negocio realmente lo requiere.

## 8. Out-of-order

- Orden fuente disponible:
- Regla para no degradar estado:
- Evento tardío de prueba:
- Estado actual esperado después del evento tardío:
- Fallback si no existe secuencia fiable:

## 9. Observabilidad

- `request_id`:
- `correlation_id`:
- provider/event operation ID no sensible:
- métricas mínimas:
- alerta por backlog:
- alerta por `outcome_unknown`:
- alerta por `failed_final`:
- runbook:

## 10. Pruebas mínimas

| Caso | Evidencia | Resultado |
| --- | --- | --- |
| Mismo evento inbound dos veces | | NOT EVALUATED |
| Dos workers reclaman simultáneamente | | NOT EVALUATED |
| Timeout después de iniciar dispatch | | NOT EVALUATED |
| Evento fuera de orden | | NOT EVALUATED |
| Reprocess de la misma operación | | NOT EVALUATED |
| Duplicado de idempotency key outbound | | NOT EVALUATED |
| Caída antes de cruzar frontera externa | | NOT EVALUATED |
| Caída después de cruzar frontera externa | | NOT EVALUATED |

`NOT EVALUATED` no equivale a PASS.
