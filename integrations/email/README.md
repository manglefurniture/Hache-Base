# Correo transaccional por API HTTPS

Patrón reutilizable para alertas operativas, confirmaciones y correos transaccionales sin acoplar el dominio del proyecto a SMTP ni a un proveedor concreto.

## Cuándo usarlo

Preferir una API HTTPS sobre puerto 443 cuando el proveedor lo soporte, especialmente en VPS/cloud donde la salida SMTP puede estar restringida o cuando se quiera simplificar observabilidad y rotación de credenciales.

SMTP sigue siendo válido si el entorno lo soporta, pero no debe asumirse conectividad a 25/465/587 sin comprobarla desde staging/producción.

## Componentes

- `TransactionalMailer.php`: contrato mínimo del proyecto.
- `ResendMailer.php`: adaptador de referencia para Resend mediante HTTPS/cURL.

El adaptador no lee variables de entorno directamente. El proyecto destino debe construirlo con configuración propia; así el código permanece testeable y desacoplado del mecanismo usado para secretos.

## Configuración sugerida

```env
MAIL_TRANSPORT=https-api
MAIL_PROVIDER=resend
MAIL_API_KEY=
MAIL_FROM=no-reply@example.com
MAIL_FROM_NAME=Example App
MAIL_ALERT_TO=
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
6. Probar una entrega real desde el entorno donde correrá la aplicación; un `200` del proveedor confirma aceptación, no necesariamente lectura del destinatario.

## Cobertura del evento y momento de envío

La notificación debe modelarse alrededor del **evento de negocio confirmado**, no alrededor de un endpoint concreto. Si el mismo evento puede producirse desde formulario público, panel interno, API, importación o job, el proyecto debe inventariar todos esos entry points y decidir explícitamente cuáles notifican.

Reglas reutilizables:

1. No enviar una confirmación antes de que el estado de negocio sea durable. En flujos transaccionales, enviar después del `commit` o usar un outbox persistido dentro de la misma transacción y procesado después.
2. Una falla del proveedor de correo posterior al `commit` se registra y puede reintentarse, pero no debe deshacer la operación ya confirmada.
3. Centralizar, cuando sea razonable, la construcción del evento/notificación para evitar que cada ruta implemente una versión distinta del mismo correo.
4. Mantener una regresión de cobertura que detecte cuando aparece un nuevo entry point capaz de confirmar el evento sin declarar si dispara notificación o por qué no debe hacerlo.
5. Si una ruta confirma varias operaciones en lote, definir de forma explícita si la notificación es por operación, por lote o mediante resumen; no inferirlo accidentalmente desde el controlador HTTP.

Este contrato no obliga a enviar sincrónicamente. Un outbox/worker es preferible cuando la latencia, reintentos o volumen lo justifican; la invariancia importante es que la decisión de notificar quede ligada al evento confirmado y no al nombre de la ruta que lo originó.

## Secretos en PHP-FPM

Dos opciones válidas según el proyecto:

- `.env` protegido y cargado explícitamente por la aplicación;
- variables inyectadas por el pool PHP-FPM/systemd, consumidas con `getenv()`.

Si se usa una variable temporal en shell para instalar una credencial, evitar imprimirla y ejecutar `unset` al terminar.
