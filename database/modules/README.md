# Módulos de datos

Estos esquemas son **plantillas**, no migraciones que deban aplicarse automáticamente a todos los proyectos.

## `core.sql`

Modelo genérico para servicios recurrentes: organizaciones, sedes, usuarios, clientes, servicios, planes, horarios, inscripciones, pagos y sesiones.

## `recurring-operations.sql`

Extensión opcional para negocios que manejan asistencia, ausencias y sesiones de reposición/reemplazo.

## `payment-gateway-credentials.sql`

Plantilla opcional para proyectos con cobros externos que necesitan rotar credenciales sin romper pagos históricos.

Incluye:

- versiones inmutables de credenciales;
- puntero a la versión actual;
- secretos cifrados en reposo por la aplicación;
- soporte deliberado para una versión legacy `token-only` cuando una instalación antigua no tenía Webhook Secret;
- FK histórica con `ON DELETE RESTRICT`;
- ejemplo conceptual para ligar la tabla de dominio a `payment_credential_id`.

Antes de usarla, leer `integrations/payments/CREDENTIAL-VERSIONING.md`. La tabla de dominio puede ser pedidos, reservas, suscripciones u otra obligación; no copiar literalmente el ejemplo `orders` si no corresponde al proyecto.

## `async-inbox-outbox.sql`

Plantilla opt-in P0-06 para integraciones repetibles o asíncronas que justifican persistencia de dedupe/retry.

Incluye:

- `integration_inbox` con unicidad `(source, external_event_id)`;
- `integration_outbox` con `idempotency_key` única, claims y `dispatch_started_at`;
- `integration_idempotency_claims` para efectos que necesitan un claim persistente sin una outbox completa;
- `request_id`/`correlation_id` para trazabilidad;
- vocabulario de `operation_state` compatible con `AsyncOperationState`.

No crea workers, cron, Redis ni colas. Antes de adoptarla, completar `templates/INBOX-OUTBOX-IDEMPOTENCY.md` y leer `integrations/async/README.md`. El proyecto debe definir retención, PII, cleanup, backoff, recuperación de claims y reconciliación.

## `email-delivery-status.sql`

Extensión opt-in P1-08 para proyectos que necesitan distinguir intención, aceptación del proveedor y entrega real de correo.

Incluye una proyección `email_delivery_messages` alineada con COM-001/COM-002:

- canal y `local_message_key` estable para dedupe local;
- `business_operation_id`;
- template y versión;
- destinatario normalizado (PII que exige retención/acceso definidos por proyecto);
- provider message ID nullable mientras el estado es `requested`;
- estados `requested`, `accepted`, `delayed`, `delivered`, `bounced`, `failed` y `suppressed`;
- `attempt_count` de envío y timestamps por estado;
- request/correlation IDs;
- sin body, variables de plantilla ni raw webhook obligatorios.

El historial/dedupe/reprocess de eventos entrantes se apoya en `integration_inbox` de P0-06 en vez de duplicar otra tabla de eventos. El reprocess reutiliza la misma fila/`external_event_id`; no equivale a reenviar el correo. No existe FK obligatoria entre inbox y esta proyección para tolerar la carrera en la que el webhook llega antes de que se persista la aceptación local.

Antes de adoptarla, leer `integrations/email/README.md`, definir retención/PII y diseñar el worker/transacción concreta del proyecto.

## Selección

Un restaurante, por ejemplo, podría reutilizar organizaciones, sedes, usuarios y clientes pero reemplazar inscripciones/sesiones por mesas, órdenes e inventario. Un SPA podría reutilizar sedes, clientes, servicios, pagos y adaptar horarios a citas.

No copiar tablas que no correspondan al negocio. Antes de convertir una plantilla en migración:

1. definir la matriz de permisos;
2. decidir si el proyecto es multisede;
3. documentar reglas de negocio;
4. ajustar relaciones e índices;
5. añadir controles de integridad por sede;
6. probar sobre staging/clon.
