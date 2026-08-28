# Pagos externos y webhooks

Patrón reutilizable para integrar proveedores de pago sin confiar ciegamente en el navegador ni en el cuerpo de un webhook.

## Objetivo

Separar cinco responsabilidades:

1. resolver de forma segura la versión de credenciales que usará la operación;
2. iniciar la intención/preferencia de pago;
3. recibir y autenticar eventos del proveedor;
4. consultar el recurso autoritativo al proveedor;
5. aplicar el resultado local de forma transaccional e idempotente.

El proveedor concreto (Mercado Pago, Stripe u otro) debe vivir detrás de un adaptador del proyecto. Hache-Base documenta el contrato y los controles, no las reglas comerciales de un proveedor específico.

## Documentos del módulo

- `CREDENTIAL-VERSIONING.md`: rotación segura, credenciales históricas, transición desde `.env`, locks y reconciliación por versión.
- `RESERVATIONS-IDEMPOTENCY.md`: TTL de reservas, idempotencia y concurrencia.
- `CredentialCipher.php`: cifrado AES-256-GCM reutilizable para secretos en reposo.
- `WebhookHmac.php`: utilidades genéricas para HMAC; cada proveedor define su manifest exacto.
- `database/modules/payment-gateway-credentials.sql`: plantilla de esquema para versiones inmutables y puntero de configuración.

## Flujo recomendado

`RESOLVER VERSIÓN -> CHECKOUT -> RESERVA LOCAL -> LIGAR OPERACIÓN A CREDENCIAL -> PREFERENCIA EXTERNA -> WEBHOOK FIRMADO -> CONSULTA AL PROVEEDOR CON ESA VERSIÓN -> LOCK LOCAL -> UPSERT PAGO -> VALIDAR MONTO/MONEDA -> TRANSICIÓN DE ESTADO -> EFECTOS SECUNDARIOS`

### 1. Credenciales y checkout

- No sobreescribir credenciales usadas por operaciones existentes; crear versiones inmutables.
- El pedido/obligación local debe guardar la versión de credenciales antes de crear el recurso externo.
- Serializar checkout y rotación de configuración con locks compatibles: lectura compartida para checkout y `FOR UPDATE` o equivalente para cambio administrativo.
- Recalcular precios y disponibilidad en servidor; nunca confiar en importes enviados por el cliente.
- Normalizar artículos repetidos antes de reservar.
- Bloquear filas (`FOR UPDATE` o mecanismo equivalente) al comprobar inventario/cupo.
- Crear una referencia externa local única para correlacionar proveedor y pedido.

Consultar `CREDENTIAL-VERSIONING.md` para la transición segura desde variables legacy de entorno.

### 2. Reserva temporal

Si existe inventario, cupos o recursos escasos, reservarlos por un TTL definido. Una reserva abandonada debe poder liberarse sin intervención manual. Consultar `RESERVATIONS-IDEMPOTENCY.md`.

Cuando el proveedor soporte expiración de preferencias/intents, alinear esa vigencia con el TTL local para evitar pagos tardíos sobre recursos ya liberados.

### 3. Webhook

- Rechazar métodos no esperados.
- Validar firma/autenticidad antes de aplicar mutaciones.
- Conservar el cuerpo raw si el esquema de firma del proveedor lo requiere.
- No confiar solo en `status`, importe o referencia recibidos en el webhook: consultar el pago/evento directamente al proveedor usando su ID.
- Usar comparación constante (`hash_equals`) para firmas HMAC.
- Si existen versiones históricas, validar la firma contra versiones elegibles y consultar al proveedor con el token de la **misma** versión que validó la firma.
- Excluir versiones legacy que no tengan Webhook Secret de los candidatos de firma.
- No limitar eventos históricos a la credencial actualmente activa.
- `WebhookHmac.php` aporta utilidades genéricas para headers clave=valor y HMAC-SHA256; cada adaptador debe construir exactamente el manifest exigido por su proveedor.

### 4. Retorno del comprador

La ruta de retorno/refresh debe consultar al proveedor con la versión vinculada a la operación. No usar ciegamente la credencial actual, porque el cliente puede volver después de una rotación de cuenta o token.

### 5. Aplicación local

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

Una rotación de credenciales no debe impedir procesar un refund/chargeback tardío. La operación conserva la versión histórica necesaria para consultar o autenticar el evento.

## Configuración sugerida

```env
PAYMENT_PROVIDER=
PAYMENT_ACCESS_TOKEN=
PAYMENT_WEBHOOK_SECRET=
PAYMENT_GATEWAY_CONFIG_KEY=
PAYMENT_RESERVATION_TTL_MINUTES=30
```

`PAYMENT_ACCESS_TOKEN` y `PAYMENT_WEBHOOK_SECRET` pueden actuar como fallback/bootstrap legacy antes de que la configuración persistida tome control. Después del takeover, evitar lecturas directas dispersas desde `.env`.

`PAYMENT_GATEWAY_CONFIG_KEY` debe ser aleatoria, estable y externa a la base de datos. No rotarla sin un procedimiento de recifrado de todas las versiones históricas.

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
- carrera de dos checkouts por la última unidad/cupo;
- rotación de credenciales sin romper operaciones antiguas;
- transición legacy con token + secreto;
- transición legacy con solo token;
- retorno usando la versión ligada a la operación;
- webhook histórico después de cambiar cuenta;
- desactivación que bloquee nuevos checkouts sin bloquear eventos históricos.
