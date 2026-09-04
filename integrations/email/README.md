# Correo transaccional por API HTTPS

Patrón reutilizable para alertas operativas, confirmaciones y correos transaccionales sin acoplar el dominio del proyecto a SMTP ni a un proveedor concreto.

## Cuándo usarlo

Preferir una API HTTPS sobre puerto 443 cuando el proveedor lo soporte, especialmente en VPS/cloud donde la salida SMTP puede estar restringida o cuando se quiera simplificar observabilidad y rotación de credenciales.

SMTP sigue siendo válido si el entorno lo soporta, pero no debe asumirse conectividad a 25/465/587 sin comprobarla desde staging/producción.

## Componentes

- `TransactionalMailer.php`: contrato mínimo del proyecto.
- `ResendMailer.php`: adaptador de referencia para Resend mediante HTTPS/cURL.
- `EmailDeliveryStatus.php`: vocabulario P1-08 `requested/accepted/delayed/delivered/bounced/failed/suppressed` y defensa contra eventos tardíos/regresiones/conflictos terminales.
- `ResendWebhook.php`: verificación Svix del body RAW y normalización mínima de eventos de entrega de Resend.
- `database/modules/email-delivery-status.sql`: proyección opt-in de trazabilidad COM-001/COM-002; usa `integration_inbox` de P0-06 para dedupe, intentos de webhook y reprocess.

Los adaptadores no leen variables de entorno directamente. El proyecto destino debe construirlos con configuración propia; así el código permanece testeable y desacoplado del mecanismo usado para secretos.

## Configuración sugerida

```env
MAIL_TRANSPORT=https-api
MAIL_PROVIDER=resend
MAIL_API_KEY=
MAIL_FROM=no-reply@example.com
MAIL_FROM_NAME=Example App
MAIL_ALERT_TO=
MAIL_WEBHOOK_SECRET=
```

No versionar valores reales. Verificar en el proveedor el dominio o subdominio exacto usado como remitente y completar los registros de autenticación requeridos (por ejemplo DKIM/SPF y, cuando corresponda, DMARC).

## Uso de referencia

```php
use HacheBase\Integrations\Email\ResendMailer;

$mailer = new ResendMailer(
    getenv('MAIL_API_KEY') ?: '',
    getenv('MAIL_FROM') ?: '',
    getenv('MAIL_FROM_NAME') ?: ''
);

$messageId = $mailer->sendText(
    'operaciones@example.com',
    'Evento confirmado',
    'La operación fue procesada correctamente.'
);
```

## Reglas operativas

1. El correo es un efecto secundario: una falla de notificación no debe revertir automáticamente una transacción de negocio ya confirmada, salvo que el correo sea parte explícita del contrato transaccional.
2. Si un webhook o job puede repetirse, reclamar primero el envío de forma idempotente y registrar el identificador/fecha de notificación.
3. Si el envío falla después del claim, liberar o marcar el claim como reintentable de forma controlada.
4. No imprimir API keys, tokens ni cuerpos con datos sensibles en logs públicos.
5. Registrar errores del proveedor por canal privado y aplicar reintentos con límite/backoff cuando el flujo lo requiera.
6. Probar una entrega real desde el entorno donde correrá la aplicación; un `2xx` del proveedor confirma aceptación, no entrega al destinatario.

## Cobertura del evento y momento de envío

La notificación debe modelarse alrededor del **evento de negocio confirmado**, no alrededor de un endpoint concreto. Si el mismo evento puede producirse desde formulario público, panel interno, API, importación o job, el proyecto debe inventariar todos esos entry points y decidir explícitamente cuáles notifican.

Reglas reutilizables:

1. No enviar una confirmación antes de que el estado de negocio sea durable. En flujos transaccionales, enviar después del `commit` o usar un outbox persistido dentro de la misma transacción y procesado después.
2. Una falla del proveedor de correo posterior al `commit` se registra y puede reintentarse, pero no debe deshacer la operación ya confirmada.
3. Centralizar, cuando sea razonable, la construcción del evento/notificación para evitar que cada ruta implemente una versión distinta del mismo correo.
4. Mantener una regresión de cobertura que detecte cuando aparece un nuevo entry point capaz de confirmar el evento sin declarar si dispara notificación o por qué no debe hacerlo.
5. Si una ruta confirma varias operaciones en lote, definir de forma explícita si la notificación es por operación, por lote o mediante resumen; no inferirlo accidentalmente desde el controlador HTTP.

Este contrato no obliga a enviar sincrónicamente. Un outbox/worker es preferible cuando la latencia, reintentos o volumen lo justifican; la invariancia importante es que la decisión de notificar quede ligada al evento confirmado y no al nombre de la ruta que lo originó.

## P1-08 — estado real de entrega y webhooks

P1-08 materializa el roadmap sin crear un proveedor obligatorio ni activar infraestructura global. La fuente normativa sigue siendo el Standard: para comunicaciones transaccionales, COM-001 exige trazabilidad persistente y COM-002 exige distinguir estados reales cuando el proveedor los soporte.

### Registro de comunicación

Antes de llamar al proveedor, un proyecto que adopta esta Extension crea una fila `requested` con la metadata mínima necesaria para trazabilidad:

- canal;
- `local_message_key` estable para una única notificación lógica;
- `business_operation_id` que la liga al evento/CUF de negocio;
- template y versión;
- destinatario normalizado;
- proveedor;
- estado;
- `attempt_count` de envío;
- timestamps.

El destinatario normalizado es PII necesaria para COM-001: debe tener acceso, retención y eliminación definidos por el proyecto. Esto **no** autoriza guardar body completo, variables de plantilla, headers arbitrarios ni raw webhook. P1-09 ampliará el inventario/retención de datos, pero P1-08 no puede omitir un campo requerido por la fuente normativa.

`provider_message_id` puede ser `NULL` mientras la fila está `requested`. Cuando `ResendMailer::sendText()` devuelve el `email_id`, el proyecto enlaza ese ID y mueve la fila a `accepted`: significa **aceptado por el proveedor**, no entregado.

### Estados de entrega

El contrato admite:

- `requested` — intención durable antes de cruzar la frontera externa;
- `accepted` — el proveedor aceptó el envío (`sent` en proveedores que usan ese nombre);
- `delayed` — la entrega sigue pendiente/retrasada;
- `delivered` — el proveedor reporta entrega al servidor receptor;
- `bounced` — rebote reportado por el proveedor;
- `failed` — fallo final reportado por el proveedor;
- `suppressed` — el proveedor decidió no enviar cuando soporta esa señal.

El adaptador de referencia normaliza estos eventos de Resend:

| Evento Resend | Estado Hache-Base |
| --- | --- |
| `email.sent` | `accepted` |
| `email.delivery_delayed` | `delayed` |
| `email.delivered` | `delivered` |
| `email.bounced` | `bounced` |
| `email.failed` | `failed` |
| `email.suppressed` | `suppressed` |

Otros eventos como open/click/complaint no se convierten silenciosamente en estados de entrega. Un endpoint compartido puede verificarlos y marcarlos como `supported=false`, pero debe decidir explícitamente si los procesa en otra Extension.

### Verificación antes de confiar

Resend firma webhooks con el formato Svix. `ResendWebhook` exige:

- body HTTP **RAW exacto**, antes de `json_decode` o reserialización;
- headers `svix-id`, `svix-timestamp` y `svix-signature` (case-insensitive);
- secret `whsec_...` configurado fuera del repo;
- HMAC válido y timestamp dentro de la tolerancia configurada (300 s por defecto).

No insertar en inbox ni mutar estado antes de verificar. La firma válida demuestra autenticidad del evento recibido, pero no elimina la necesidad de reconciliar cuando el dominio exige consultar una fuente autoritativa.

### Persistencia mínima del webhook

Después de verificar, `ResendWebhook::verifyAndNormalize()` conserva solamente metadata de evento apta para inbox/proyección:

- proveedor;
- ID externo del evento (`svix-id`);
- tipo de evento;
- `email_id` del proveedor para eventos soportados;
- estado normalizado;
- timestamp declarado por el proveedor;
- SHA-256 del body RAW.

El normalizador no devuelve destinatario, remitente, asunto, tags ni body. El registro COM-001 obtiene el destinatario normalizado y template/version del contexto durable del **envío**, no copiándolos desde un webhook. El raw webhook puede contener PII adicional: si un proyecto decide conservarlo necesita justificar retención, cifrado/acceso y cleanup.

### Inbox, orden y proyección

Adopción recomendada:

1. verificar firma sobre body RAW;
2. insertar una única fila en `integration_inbox` con `(source, external_event_id)`; para Resend, `external_event_id` es `svix-id`;
3. usar `aggregate_key = provider_message_id`, `occurred_at` del proveedor y `payload_sha256` del normalizador;
4. reclamar la misma fila de inbox antes de mutar;
5. actualizar `email_delivery_messages` solo si el evento realmente avanza la proyección;
6. marcar la inbox procesada dentro de la estrategia transaccional del proyecto.

`EmailDeliveryStatus::apply()` compara timestamp **del proveedor**, nunca `created_at` local. Un evento más viejo no degrada el agregado; tampoco permite volver de `delayed` a `accepted/requested`. `delivered`, `bounced`, `failed` y `suppressed` son terminales para actualización automática: si llega después un terminal distinto, la proyección no se pisa y exige reconciliación. Dos estados distintos con la misma marca temporal también se consideran conflicto.

No existe FK obligatoria desde inbox a la proyección porque un webhook puede competir con la escritura local de aceptación. Esa carrera se resuelve por proyecto mediante upsert/reconciliación, sin perder el evento deduplicado.

### Retry de envío vs reprocess de webhook

Son operaciones distintas:

- `email_delivery_messages.attempt_count` cuenta intentos de **envío** de la misma notificación lógica;
- `integration_inbox.attempts` cuenta intentos de **procesamiento del evento entrante**.

**Reprocess** vuelve a procesar la misma fila verificada de `integration_inbox` después de un fallo local/reconciliación:

- conserva `external_event_id` y la misma fila;
- incrementa inbox `attempts` y guarda motivo/error según P0-06;
- no crea un evento duplicado;
- no llama `sendText()` otra vez;
- vuelve a aplicar la proyección de forma idempotente.

Un retry de envío solo puede ocurrir cuando la operación saliente/outbox demuestra que repetir es seguro y el fallo es temporal. `delayed` significa que el proveedor todavía intenta entregar y **no** autoriza reenviar. Hard bounce y suppression no se reintentan ciegamente; `failed` requiere clasificación/reconciliación antes de cualquier nueva operación.

Reenviar deliberadamente después de un resultado final es una **nueva decisión de negocio**. Debe mantener trazabilidad con la operación original y usar una nueva operación lógica/idempotency key cuando corresponda; nunca usar replay/reprocess de webhook como atajo para duplicar el envío.

### Alcance de cumplimiento

La disponibilidad de esta Extension no auto-aprueba COM-001…COM-005. En particular:

- COM-001 necesita que el proyecto realmente persista y consulte el registro;
- COM-003 requiere templates/versiones y muestras reales revisadas;
- COM-004 requiere política de retry temporal y dedupe del proyecto real;
- COM-005, cuando aplica a nivel C, necesita fallback **probado**; Hache-Base no inventa un canal alternativo.

## Secretos en PHP-FPM

Dos opciones válidas según el proyecto:

- `.env` protegido y cargado explícitamente por la aplicación;
- variables inyectadas por el pool PHP-FPM/systemd, consumidas con `getenv()`.

Si se usa una variable temporal en shell para instalar una credencial, evitar imprimirla y ejecutar `unset` al terminar.
