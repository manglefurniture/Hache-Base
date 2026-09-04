# Pruebas de integración

Cada proyecto debe añadir casos concretos para sus flujos críticos. La base exige cubrir, cuando apliquen:

- autenticación válida e inválida;
- permiso permitido y denegado;
- aislamiento entre sedes/organizaciones;
- escrituras con fixtures aislados;
- pagos, invalidaciones y recálculos financieros;
- migraciones sobre un clon/staging;
- endpoints internos con y sin Bearer token;
- integraciones externas sin mezclar secretos con fixtures.

## Cobertura base de integraciones

- `ResendMailerTest.php`: contrato offline del transporte HTTPS.
- `EmailDeliveryStatusTest.php`: orden de eventos del proveedor, stale/duplicate/conflict y vocabulario P1-08.
- `ResendWebhookTest.php`: firma Svix offline, raw body, tolerancia temporal, mapping Resend y minimización de PII.
- `EmailDeliveryMariaDbTest.sh`: dedupe por evento, proyección que no retrocede y reprocess de la misma inbox sin reenviar.
- `WebhookHmacTest.php`: parsing y verificación HMAC-SHA256 genérica para integraciones que usan ese formato.
- `CredentialCipherTest.php`: AES-256-GCM, manipulación/wrong-key y invariantes mínimas de la plantilla de credenciales versionadas.

Estas pruebas no sustituyen las pruebas sandbox/staging específicas de cada proveedor ni una entrega real hacia un buzón controlado del proyecto.

## Regla de datos

Las pruebas con escritura no deben ejecutarse sobre datos históricos reales. Usar una base de staging, clon o fixtures desechables y verificar recuentos/estado antes y después cuando el flujo pueda afectar información existente.
