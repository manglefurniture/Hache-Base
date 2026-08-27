# Pagos externos y webhooks

Patrón reutilizable para integrar proveedores de pago sin confiar ciegamente en el navegador ni en el cuerpo de un webhook.

## Objetivo

Separar cuatro responsabilidades:

1. iniciar la intención/preferencia de pago;
2. recibir y autenticar eventos del proveedor;
3. consultar el recurso autoritativo al proveedor;
4. aplicar el resultado local de forma transaccional e idempotente.

El proveedor concreto (Mercado Pago, Stripe u otro) debe vivir detrás de un adaptador del proyecto. Hache-Base documenta el contrato y los controles, no las reglas comerciales de un proveedor específico.

## Flujo recomendado

`CHECKOUT -> RESERVA LOCAL -> PREFERENCIA EXTERNA -> WEBHOOK FIRMADO -> CONSULTA AL PROVEEDOR -> LOCK LOCAL -> UPSERT PAGO -> VALIDAR MONTO/MONEDA -> TRANSICIÓN DE ESTADO -> EFECTOS SECUNDARIOS`

### 1. Checkout

- Recalcular precios y disponibilidad en servidor; nunca confiar en importes enviados por el cliente.
- Normalizar artículos repetidos antes de reservar.
- Bloquear filas (`FOR UPDATE` o mecanismo equivalente) al comprobar inventario/cupo.
- Crear una referencia externa local única para correlacionar proveedor y pedido.

### 2. Reserva temporal

Si existe inventario, cupos o recursos escasos, reservarlos por un TTL definido. Una reserva abandonada debe poder liberarse sin intervención manual. Consultar `RESERVATIONS-IDEMPOTENCY.md`.

### 3. Webhook

- Rechazar métodos no esperados.
- Validar firma/autenticidad antes de aplicar mutaciones.
- Conservar el cuerpo raw si el esquema de firma del proveedor lo requiere.
- No confiar solo en `status`, importe o referencia recibidos en el webhook: consultar el pago/evento directamente al proveedor usando su ID.
- Usar comparación constante (`hash_equals`) para firmas HMAC.
- `WebhookHmac.php` aporta utilidades genéricas para headers clave=valor y HMAC-SHA256; cada adaptador debe construir exactamente el manifest exigido por su proveedor.

### 4. Aplicación local

Dentro de una transacción:

- bloquear el pedido/obligación local;
- hacer UPSERT del pago usando un ID externo con restricción `UNIQUE`;
- validar referencia externa, importe y moneda;
- definir una máquina de estados explícita;
- no degradar una operación ya confirmada por un webhook tardío de estado inferior;
- registrar incidencias cuando el proveedor confirme algo que no coincide con el recurso local.

## Efectos secundarios

Correo, WhatsApp, n8n, facturación y otros efectos deben ejecutarse después de confirmar el estado central. Un error de notificación no debe convertir un pago aprobado en fallido.

Cuando el proveedor reintente un webhook, esos efectos deben ser idempotentes. Usar un claim/fecha/ID de efecto o una outbox si la criticidad lo justifica.

## Reembolsos y contracargos

No asumir que restaurar inventario es siempre correcto. El proyecto debe definir qué ocurre si el artículo ya fue entregado, consumido o transferido. Registrar el evento y aplicar la política de dominio correspondiente.

## Configuración sugerida

```env
PAYMENT_PROVIDER=
PAYMENT_ACCESS_TOKEN=
PAYMENT_WEBHOOK_SECRET=
PAYMENT_RESERVATION_TTL_MINUTES=30
```

Nunca versionar valores reales.

## Pruebas mínimas

- firma válida e inválida;
- webhook repetido;
- pago aprobado correcto;
- pago aprobado con importe distinto;
- pago aprobado con moneda distinta;
- evento tardío después de un estado final;
- rechazo/cancelación con reserva activa;
- expiración de reserva;
- reembolso/contracargo según la regla del negocio;
- caída del correo/notificación sin perder el estado del pago;
- carrera de dos checkouts por la última unidad/cupo.
