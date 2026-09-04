# Correo transaccional por API HTTPS

Patrón reutilizable para alertas operativas, confirmaciones y correos transaccionales sin acoplar el dominio del proyecto a SMTP ni a un proveedor concreto.

## Cuándo usarlo

Preferir una API HTTPS sobre puerto 443 cuando el proveedor lo soporte, especialmente en VPS/cloud donde la salida SMTP puede estar restringida o cuando se quiera simplificar observabilidad y rotación de credenciales.

SMTP sigue siendo válido si el entorno lo soporta, pero no debe asumirse conectividad a 25/465/587 sin comprobarla desde staging/producción.

## Componentes

- `TransactionalMailer.php`: contrato mínimo del proyecto.
- `ResendMailer.php`: adaptador de referencia para Resend mediante HTTPS/cURL.
- `EmailDeliveryStatus.php`: vocabulario P1-08 `accepted/delivered/delayed/bounced/failed` y defensa contra eventos tardíos/conflictos de timestamp.
- `ResendWebhook.php`: verificación Svix del body RAW y normalización mínima de eventos de entrega de Resend.
- `database/modules/email-delivery-status.sql`: proyección opt-in del estado actual; usa `integration_inbox` de P0-06 para dedupe, intentos y reprocess.

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

`ResendMailer::sendText()` devuelve el `email_id` asignado por el proveedor. En un proyecto que adopta P1-08, ese ID crea o enlaza una proyección `accepted`: significa **aceptado por el proveedor**, no entregado. El webhook `email.sent` puede confirmar el mismo estado.

El adaptador de referencia normaliza únicamente estos eventos de entrega:

| Evento Resend | Estado Hache-Base |
| --- | --- |
| `email.sent` | `accepted` |
| `email.delivered` | `delivered` |
| `email.delivery_delayed` | `delayed` |
| `email.bounced` | `bounced` |
| `email.failed` | `failed` |

Otros eventos como open/click/complaint no se convierten silenciosamente en estados de entrega. Un endpoint compartido puede verificarlos y marcarlos como `supported=false`, pero debe decidir explícitamente si los procesa en otra Extension.

### Verificación antes de confiar

Resend firma webhooks con el formato Svix. `ResendWebhook` exige:

- body HTTP **RAW exacto**, antes de `json_decode` o reserialización;
- headers `svix-id`, `svix-timestamp` y `svix-signature` (case-insensitive);
- secret `whsec_...` configurado fuera del repo;
- HMAC válido y timestamp dentro de la tolerancia configurada (300 s por defecto).

No insertar en inbox ni mutar estado antes de verificar. La firma válida demuestra autenticidad del evento recibido, pero no elimina la necesidad de reconciliar cuando el dominio exige consultar una fuente autoritativa.

### Persistencia mínima y privacidad

Después de verificar, `ResendWebhook::verifyAndNormalize()` conserva solamente:

- proveedor;
- ID externo del evento (`svix-id`);
- tipo de evento;
- `email_id` del proveedor para eventos soportados;
- estado normalizado;
- timestamp declarado por el proveedor;
- SHA-256 del body RAW.

No devuelve ni exige persistir destinatario, remitente, asunto, tags ni body. El raw webhook puede contener PII: si un proyecto decide conservarlo necesita justificar retención, cifrado/acceso y cleanup en su inventario de datos.

### Inbox, orden y proyección

Adopción recomendada:

1. verificar firma sobre body RAW;
2. insertar una única fila en `integration_inbox` con `(source, external_event_id)`; para Resend, `external_event_id` es `svix-id`;
3. usar `aggregate_key = provider_message_id`, `occurred_at` del proveedor y `payload_sha256` del normalizador;
4. reclamar la misma fila de inbox antes de mutar;
5. actualizar `email_delivery_messages` solo si el evento realmente avanza la proyección;
6. marcar la inbox procesada dentro de la estrategia transaccional del proyecto.

`EmailDeliveryStatus::apply()` compara timestamp **del proveedor**, nunca `created_at` local. Un evento más viejo no degrada el agregado. Dos estados distintos con la misma marca temporal se consideran conflicto y deben reconciliarse; Hache-Base no inventa una prioridad universal entre terminales.

No existe FK obligatoria desde inbox a la proyección porque un webhook puede competir con la escritura local de aceptación. Esa carrera se resuelve por proyecto mediante upsert/reconciliación, sin perder el evento deduplicado.

### Reprocess no significa reenviar

En P1-08, **reprocess** significa volver a procesar la misma fila verificada de `integration_inbox` después de un fallo local/reconciliación:

- conservar `external_event_id` y la misma fila;
- incrementar `attempts` y guardar motivo/error según P0-06;
- no crear un evento duplicado;
- no llamar `sendText()` otra vez como efecto del reprocess;
- volver a aplicar la proyección de forma idempotente.

Reenviar un correo es una **nueva operación lógica** y debe pasar por su propia decisión de negocio/outbox/idempotency key. Nunca usar un replay/reprocess de webhook como atajo para duplicar el envío.

## Secretos en PHP-FPM

Dos opciones válidas según el proyecto:

- `.env` protegido y cargado explícitamente por la aplicación;
- variables inyectadas por el pool PHP-FPM/systemd, consumidas con `getenv()`.

Si se usa una variable temporal en shell para instalar una credencial, evitar imprimirla y ejecutar `unset` al terminar.
