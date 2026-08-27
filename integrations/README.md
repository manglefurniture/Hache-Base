# Integrations

Patrones para conectar servicios externos sin acoplarlos al núcleo de la aplicación.

## Incluido

- `email/`: correo transaccional desacoplado, API HTTPS y adaptador de referencia para Resend.
- `payments/`: pagos externos, autenticación de webhooks, idempotencia y reservas temporales.
- `n8n/`: patrón aplicación ↔ n8n, reenvío de Authorization para Nginx/PHP-FPM y backup consistente para Docker + SQLite.

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

Las integraciones específicas de un negocio (por ejemplo, un asistente o workflow concreto) permanecen en ese proyecto y no entran automáticamente en Hache-Base.
