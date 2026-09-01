# P0-05 — Contrato de operaciones asíncronas

## Alcance

P0-05 introduce un lenguaje común para operaciones cuyo efecto final puede confirmarse después de la petición inicial: correo transaccional, pagos, webhooks salientes, jobs y proveedores externos.

Esta fase **no modifica** `ResendMailer`, pagos, n8n, schemas existentes ni producción. El contrato se prueba únicamente contra fixtures controlados.

## Estados Core

| Estado | Significado |
| --- | --- |
| `requested` | La aplicación creó/inició el intento. No demuestra aceptación externa. |
| `accepted` | El proveedor aceptó la solicitud. No demuestra resultado final. |
| `outcome_unknown` | Timeout, respuesta perdida o fallo parcial: no se sabe si el efecto ocurrió. |
| `retry_pending` | Existe evidencia suficiente de que un nuevo intento es seguro y está pendiente. |
| `reconciling` | Se está consultando/esperando una fuente autoritativa para resolver el resultado. |
| `confirmed` | Éxito final demostrado por evidencia autoritativa del dominio/proveedor. |
| `failed_final` | Fallo final demostrado; no debe reintentarse automáticamente. |
| `cancelled` | Cancelado antes de un efecto externo confirmado; no se usa para deshacer historia ya confirmada. |

`src/common/AsyncOperationState.php` valida el vocabulario y las transiciones base. Los proyectos pueden mapear estados específicos del proveedor, pero no deben redefinir `accepted` como éxito final.

## Regla crítica: accepted != confirmed

Un HTTP `2xx`, un message ID o un ACK puede significar solo que otro sistema recibió la petición. El CUF se considera exitoso únicamente cuando la evidencia definida por el proyecto demuestra el resultado autoritativo.

Ejemplos:

- correo: API aceptó (`accepted`) vs estado de entrega que el proveedor exponga (`confirmed` según el contrato del proyecto);
- pago: checkout/orden creada (`accepted`) vs pago verificado/autoritativo (`confirmed`);
- job: encolado/recibido (`accepted`) vs efecto final aplicado (`confirmed`).

## Ambigüedad y retry

`outcome_unknown` existe para impedir el error clásico de tratar un timeout como fallo seguro. Desde ese estado el contrato base obliga a resolver mediante `reconciling` o evidencia autoritativa; no permite pasar directamente a `retry_pending`.

`retry_pending` significa que el proyecto ya demostró que reintentar es seguro, por ejemplo por idempotency key, claim persistente o verificación autoritativa de que el efecto no ocurrió.

P0-06 implementa de forma separada y opt-in la plantilla de inbox/outbox/idempotency claim en `integrations/async/README.md` y `database/modules/async-inbox-outbox.sql`. Esa persistencia no cambia las transiciones de P0-05: únicamente aporta dedupe, claims y evidencia para aplicarlas con seguridad.

## Ledger

`templates/ASYNC-OPERATION-LEDGER.md` define los campos mínimos recomendados de operación/evento para conservar:

- estado actual;
- intentos;
- provider operation/event IDs no sensibles;
- `request_id` y `correlation_id`;
- retry/reconciliation timestamps;
- transición append-only y error seguro.

La plantilla es conceptual/opt-in. P0-06 añade un schema opcional de persistencia para proyectos que realmente lo necesitan; sigue siendo responsabilidad del proyecto definir índices finales, retención, tratamiento de PII y runbooks.

## Relación con módulos existentes

- `RequestContext` aporta request/correlation IDs.
- `StructuredLogger` aporta observabilidad operativa redactada.
- `integrations/email/README.md` ya advierte que aceptación del proveedor no equivale a entrega; P0-05 formaliza esa diferencia sin cambiar el mailer.
- `integrations/async/README.md` define dedupe, claims, out-of-order y reprocess de P0-06 sin activar workers/colas globales.
- `docs/ESTADOS-TEMPORALES-E-INTEGRIDAD.md` trata estados derivados del tiempo; no sustituye este ciclo asíncrono.

## Fixtures de P0-05

`tests/fixtures/async-operations/scenarios.json` cubre:

1. aceptación seguida de confirmación autoritativa;
2. timeout ambiguo + reconciliación;
3. fallo conocido reintentable + nuevo intento;
4. fallo final autoritativo.

Ningún fixture de P0-05 llama proveedores ni escribe DB. P0-06 añade por separado una regresión MariaDB real de la plantilla opcional.
