# Integrations

Patrones para conectar servicios externos sin acoplarlos al núcleo de la aplicación.

## Incluido

- `async/`: inbox/outbox/idempotency claim opt-in para dedupe, concurrencia, retry seguro y reconciliación.
- `email/`: correo transaccional desacoplado, API HTTPS y adaptador de referencia para Resend.
- `payments/`: pagos externos, autenticación de webhooks, idempotencia y reservas temporales.
- `n8n/`: patrón aplicación ↔ n8n, reenvío de Authorization para Nginx/PHP-FPM y backup consistente para Docker + SQLite.
- `rum/`: Web Vitals/RUM opt-in, minimizado y sin proveedor obligatorio para evidencia de campo p75.
- `observability/`: P2-01 opt-in para logs, métricas y trazas con exporter neutral, trace context estricto y sin SDK/APM obligatorio.

Cada integración debe documentar:

- propósito;
- dirección del flujo de datos;
- autenticación;
- variables de entorno;
- requisitos de red/egress del hosting;
- errores y reintentos;
- idempotencia cuando existan callbacks, jobs o webhooks repetibles;
- privacidad;
- auditoría si modifica datos;
- backup/recuperación cuando aplique;
- procedimiento para desactivarla sin romper el producto principal.

## Regla de diseño

El dominio del proyecto no debe depender directamente del SDK o formato de un proveedor. Usar adaptadores pequeños y mantener en el núcleo solo estados y reglas de negocio propias.

Un webhook autenticado sigue siendo una señal externa: para operaciones financieras, consultar el recurso autoritativo al proveedor antes de aplicar mutaciones locales cuando su API lo permita.

Inbox/outbox no son obligatorias por existir en Hache Base. Se adoptan como Extension cuando un CUF necesita dedupe persistente, efectos posteriores al commit o reprocesamiento seguro. No activar infraestructura de workers/colas por defecto.

RUM tampoco se activa por existir en Hache Base. Cada proyecto debe completar su política de telemetría, definir `shouldCollect()`, sampling, retención, collector y cobertura; Core no decide consentimiento ni convierte p75 en `PASS`.

Observability P2-01 tampoco se activa por existir en Base. El proyecto debe justificar CUF/señales, exporter, sampling, retención, coste, atributos permitidos y fallback. La frontera neutral puede adaptarse a OpenTelemetry/APM, pero Base no instala ni configura un proveedor.

Las integraciones específicas de un negocio (por ejemplo, un asistente o workflow concreto) permanecen en ese proyecto y no entran automáticamente en Hache-Base.
