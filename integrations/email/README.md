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

## Secretos en PHP-FPM

Dos opciones válidas según el proyecto:

- `.env` protegido y cargado explícitamente por la aplicación;
- variables inyectadas por el pool PHP-FPM/systemd, consumidas con `getenv()`.

Si se usa una variable temporal en shell para instalar una credencial, evitar imprimirla y ejecutar `unset` al terminar.
