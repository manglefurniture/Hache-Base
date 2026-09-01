# Async delivery — inbox, outbox e idempotency

Módulo **opt-in** de Hache Base para integraciones repetibles o asíncronas que necesitan deduplicación, claims atómicos y reprocesamiento seguro.

Implementa P0-06 del roadmap de Production Readiness. No activa colas, workers, cron, Redis ni tablas en proyectos derivados. El proyecto adopta la plantilla únicamente cuando sus Critical User Flows y su perfil de riesgo lo justifican.

## Relación con P0-05

P0-05 define el ciclo neutral de `AsyncOperationState`. P0-06 añade persistencia/claims opcionales para poder demostrar cuándo un retry es seguro.

Invariantes:

- `accepted` no equivale a `confirmed`;
- una salida `outcome_unknown` no vuelve directamente a envío;
- `retry_pending` solo se usa después de evidencia de que repetir es seguro;
- `confirmed`, `failed_final` y `cancelled` son terminales;
- un reintento de la misma operación lógica conserva la misma `idempotency_key`.

Los cambios de `operation_state` deben validarse en la aplicación con `AsyncOperationState::assertTransition()`. Los `CHECK` del schema limitan el vocabulario persistido, pero no sustituyen la validación de cada transición.

## Inbox

La inbox deduplica eventos entrantes antes de aplicar mutaciones.

La clave base es `(source, external_event_id)`. Si el proveedor no expone un ID estable, el adaptador del proyecto debe definir una clave determinista y documentar su riesgo; no inventar un ID aleatorio por recepción porque impediría detectar duplicados.

Flujo recomendado:

1. autenticar/verificar el evento antes de confiar en él;
2. insertar en `integration_inbox`;
3. si la restricción única detecta el evento existente, responder de forma compatible sin repetir la mutación;
4. reclamar el registro de forma atómica;
5. aplicar la mutación local dentro de una transacción;
6. crear cualquier efecto externo posterior mediante outbox;
7. marcar la inbox como procesada.

La inbox no convierte un webhook en fuente autoritativa. Cuando el dominio lo requiera, consultar el recurso autoritativo antes de mutar.

## Eventos fuera de orden

`source_sequence` es opcional y solo sirve cuando la fuente ofrece una secuencia/version monotónica con semántica fiable.

Un evento tardío no debe degradar el agregado. El proyecto debe usar una de estas defensas:

- comparar una versión/secuencia autoritativa y aplicar solo si avanza;
- consultar el estado actual al proveedor y derivar el resultado;
- definir una máquina de estados que rechace regresiones.

No ordenar por `created_at` local para inferir orden de negocio.

## Outbox

La outbox representa efectos salientes que deben sobrevivir a fallos después del commit de negocio.

`idempotency_key` es única y estable para una operación lógica. Si el proveedor soporta idempotency keys, reutilizar exactamente esa clave en todos los intentos de la misma operación.

Flujo recomendado:

1. persistir la mutación de negocio y la fila outbox en la misma transacción cuando el CUF requiera entrega posterior;
2. reclamar una fila elegible mediante condición atómica;
3. incrementar `attempts` solo al obtener el claim;
4. fijar `dispatch_started_at` inmediatamente antes de cruzar la frontera externa;
5. registrar el resultado usando los estados de P0-05;
6. liberar el claim únicamente después de persistir el nuevo estado.

### Fallo ambiguo

Si el proceso muere, hay timeout o se pierde la respuesta después de `dispatch_started_at`, el siguiente worker **no debe reenviar automáticamente**. Debe llevar la operación a `outcome_unknown`/`reconciling` y resolver con el proveedor o con otra evidencia autoritativa.

Un claim huérfano solo puede reciclarse para envío directo si el proyecto puede demostrar que la frontera externa todavía no se cruzó.

## Claim ligero

`integration_idempotency_claims` es una alternativa más pequeña para efectos que necesitan dedupe/claim persistente pero no justifican una outbox completa.

La unicidad `(scope_name, claim_key)` evita dos operaciones lógicas iguales. Antes de un efecto externo se debe registrar `effect_started_at`; si el resultado queda ambiguo, se conserva la misma fila/clave y se reconcilia.

No borrar un claim para "probar de nuevo" cuando pudo existir efecto externo.

## Reprocess

Reprocess no significa crear otra fila con otra clave.

Para la misma operación lógica:

- conservar la misma inbox/outbox/claim;
- conservar la misma `idempotency_key`;
- incrementar intentos;
- registrar motivo y evidencia que habilitó el nuevo intento;
- desde `reconciling`, pasar a `retry_pending` solo cuando la evidencia permita retry seguro.

`failed_final` no se reabre automáticamente. Si el negocio decide una nueva operación después de un resultado final, debe modelarla como una operación lógica nueva y auditable.

## Concurrencia

La defensa vive en servidor:

- índices `UNIQUE`;
- `INSERT IGNORE`/UPSERT consciente para dedupe;
- `UPDATE ... WHERE claim_token IS NULL ...` y comprobación de filas afectadas para claims;
- transacciones y locks cuando se muta el agregado;
- nunca depender de deshabilitar botones en UI.

Dos workers pueden competir; solo quien afecte la fila del claim está autorizado a ejecutar el efecto.

## Plantilla SQL

`database/modules/async-inbox-outbox.sql` aporta tres tablas opcionales:

- `integration_inbox`;
- `integration_outbox`;
- `integration_idempotency_claims`.

Es una **plantilla**, no una migración universal. Antes de adoptarla hay que definir retención, PII, cifrado, tamaño del payload, índices, cleanup, scheduler/worker, política de claims huérfanos y runbook de reconciliación.

`payload_json` no autoriza guardar secretos ni datos completos innecesarios.

## Pruebas

`tests/integration/InboxOutboxMariaDbTest.sh` usa MariaDB real de CI y verifica:

- evento inbox duplicado;
- competencia de dos claims sobre una misma outbox;
- bloqueo de retry ciego después de resultado ambiguo;
- evento fuera de orden que no degrada una proyección;
- reproceso sobre la misma fila/idempotency key;
- claim ligero duplicado.

No llama proveedores externos.
