# Integrations

Patrones para conectar servicios externos sin acoplarlos al núcleo de la aplicación.

## n8n

`n8n/` contiene el patrón reutilizable aplicación ↔ n8n, reenvío de Authorization para Nginx/PHP-FPM y una plantilla de backup consistente para Docker + SQLite.

Cada integración debe documentar:

- propósito;
- dirección del flujo de datos;
- autenticación;
- variables de entorno;
- errores y reintentos;
- privacidad;
- auditoría si modifica datos;
- backup/recuperación cuando aplique;
- procedimiento para desactivarla sin romper el producto principal.

Las integraciones específicas de un negocio (por ejemplo, un asistente o workflow concreto) permanecen en ese proyecto y no entran automáticamente en Hache-Base.
