# Versionado seguro de credenciales de pago

Este patrón evita que un cambio de cuenta, token o secreto rompa pagos ya iniciados, devoluciones, contracargos o notificaciones tardías.

Aplica cuando una integración de pagos crea recursos externos que pueden seguir vivos después de rotar credenciales: preferencias, sesiones, intents, links, cargos, reembolsos o eventos equivalentes.

## Principio central

**Una credencial usada por una operación financiera no se sobreescribe. Se versiona.**

La configuración actual solo apunta a una versión. Cada operación local conserva la versión con la que nació.

## Invariantes obligatorias

1. **Versiones inmutables.** Cambiar token, secreto, ambiente, public key o cuenta crea una fila nueva. No actualizar secretos históricos en sitio.
2. **Vínculo operación → credencial.** El pedido, obligación o recurso local guarda `payment_credential_id` antes de crear el recurso externo.
3. **Rotación serializada.** Checkout toma lock compartido sobre la configuración mientras liga la operación a una versión; el cambio administrativo toma lock exclusivo (`FOR UPDATE` o equivalente).
4. **Retorno por versión.** La ruta de retorno/refresh consulta al proveedor con la credencial vinculada a esa operación, no con la credencial actual.
5. **Webhook histórico.** La firma se valida contra versiones históricas elegibles y, tras hacer match, la consulta autoritativa al proveedor usa el Access Token de esa misma versión.
6. **No mezclar firma y token.** Nunca validar con el secreto de una versión y consultar el pago con el token de otra.
7. **Versiones token-only solo para legado.** Si una instalación antigua tenía Access Token pero no Webhook Secret, preservar el token como versión histórica para retorno/consulta. Esa versión se excluye de candidatos de webhook y nunca puede quedar activa para nuevos checkouts.
8. **Activación estricta.** Una versión activa para nuevos pagos debe tener al menos el conjunto de secretos exigido por el proveedor; para un proveedor con webhook firmado: Access Token + Webhook Secret.
9. **Clave maestra fuera de BD.** Los secretos se cifran en reposo con una clave estable del servidor (`PAYMENT_GATEWAY_CONFIG_KEY` o equivalente). La clave no se guarda junto al ciphertext.
10. **No rotar la clave maestra sin plan.** Cambiarla sin recifrar todas las versiones hace ilegibles las credenciales históricas.
11. **Historial retenido.** Una versión referenciada por operaciones no se borra. Usar FK con `ON DELETE RESTRICT` o una protección equivalente.
12. **Deshabilitar no borra historia.** Apagar la pasarela bloquea nuevos checkouts, pero no impide procesar webhooks, retornos, refunds o chargebacks de operaciones antiguas.

## Modelo mínimo

Usar la plantilla `database/modules/payment-gateway-credentials.sql` como referencia.

La estructura conceptual es:

- `payment_gateway_credentials`: versiones inmutables cifradas;
- `payment_gateway_config`: estado actual y puntero a la versión vigente;
- tabla de dominio (`orders`, `bookings`, `subscriptions`, etc.): FK `payment_credential_id` a la versión utilizada.

Hache-Base no impone el nombre de la tabla de dominio.

## Secuencia segura de checkout

```text
BEGIN
  LOCK compartido de payment_gateway_config
  resolver versión actual
  validar que está activa y completa
  validar negocio/inventario/cupo
  crear operación local con payment_credential_id
COMMIT

crear preferencia/intención externa usando el token de ESA versión
persistir ID externo / URL / metadatos
```

El recurso local ya está ligado a la versión antes de que el proveedor pueda generar un pago. Si la creación externa falla, aplicar la política de cancelación/liberación definida por el proyecto.

## Secuencia segura de cambio de credenciales

```text
BEGIN
  SELECT config ... FOR UPDATE

  si es la primera toma de control desde .env:
    si existe Access Token legacy:
      crear versión histórica, incluso si no existe Webhook Secret
      ligar operaciones antiguas aún sin versión a esa credencial legacy

  calcular credenciales efectivas
  validar nueva cuenta/token contra el proveedor cuando exista endpoint de identidad
  exigir secretos necesarios si quedará activa
  insertar NUEVA versión
  actualizar puntero current_credential_id
COMMIT
```

La combinación lock compartido/exclusivo elimina la carrera entre un checkout que todavía usa la cuenta anterior y un administrador que cambia la cuenta.

## Transición desde `.env`

El fallback de entorno es una **compatibilidad de bootstrap**, no la fuente permanente después de que el panel/configuración persistida tome control.

Reglas:

- antes del primer guardado persistido, el proyecto puede usar las variables legacy;
- en la primera transición, preservar cualquier Access Token que haya podido crear recursos externos;
- si también existe Webhook Secret, esa versión puede participar en resolución histórica de webhooks;
- si no existe Webhook Secret, conservarla para consultas por retorno y excluirla de firma de webhook;
- después del takeover, la base de datos es autoritativa para la configuración de la pasarela;
- retirar variables legacy solo después de verificar que ninguna ruta depende directamente de ellas.

## Webhook con varias versiones

Proceso recomendado:

1. parsear firma y manifest exactamente como exige el proveedor;
2. obtener las versiones históricas retenidas;
3. omitir versiones sin Webhook Secret o sin token de consulta;
4. calcular HMAC/firma con cada secreto;
5. cuando una firma coincide, consultar el pago con el token de **esa misma versión**;
6. si varias versiones comparten secreto y el primer token no puede leer el pago, continuar con las demás versiones que compartan firma válida;
7. aplicar el pago local de forma idempotente y transaccional.

No limitar el webhook a la credencial actualmente activa.

## Retorno del comprador

Si la operación tiene `payment_credential_id`, resolver esa versión exacta. Solo operaciones realmente legacy y aún no migradas pueden usar un fallback temporal.

Esto permite reconciliar un pago antiguo aunque la cuenta activa haya cambiado.

## Cifrado

`CredentialCipher.php` ofrece el sobre reutilizable AES-256-GCM. El proyecto debe inyectarle una clave estable del entorno.

Ejemplo conceptual:

```php
$cipher = new CredentialCipher((string) env('PAYMENT_GATEWAY_CONFIG_KEY'));
$encryptedToken = $cipher->encrypt($accessToken);
$accessToken = $cipher->decrypt($encryptedToken);
```

Nunca renderizar de vuelta Access Tokens ni Webhook Secrets en inputs del panel. Un campo vacío al editar debe significar “conservar el secreto actual”, no “mostrarlo para editar”.

## Pruebas mínimas adicionales

Además de las pruebas generales de pagos:

- cifrado round-trip y rechazo de ciphertext alterado;
- cambio de clave debe impedir descifrado;
- rotación crea una versión nueva sin alterar la anterior;
- checkout queda vinculado a la versión leída bajo lock;
- cambio concurrente de configuración no deja una operación sin versión;
- primera transición preserva un legacy con token + secreto;
- primera transición preserva un legacy con **solo token**;
- una versión token-only no participa en webhook;
- retorno usa la versión del pedido, no la actual;
- webhook antiguo sigue conciliando después de rotar cuenta;
- refund/chargeback tardío usa la versión histórica correcta;
- desactivar la pasarela impide nuevos checkouts pero no eventos históricos.

## Checklist de despliegue

1. Añadir la tabla de versiones y el puntero de configuración.
2. Añadir FK de versión a la tabla de dominio.
3. Definir una `PAYMENT_GATEWAY_CONFIG_KEY` aleatoria y estable en el servidor.
4. Verificar el checkout legacy antes del primer takeover.
5. Ejecutar la primera transición preservando credenciales legacy.
6. Configurar credenciales nuevas desde el mecanismo administrativo.
7. Probar checkout en sandbox/test.
8. Probar webhook firmado real o sandbox.
9. Probar retorno con una operación ligada a una versión histórica.
10. No eliminar credenciales antiguas mientras existan operaciones que puedan generar eventos financieros posteriores.

## Qué NO generalizar

Hache-Base estandariza seguridad, persistencia, rotación y reconciliación. Cada adaptador conserva:

- endpoints del proveedor;
- formato exacto de firma;
- campos de preferencia/intención;
- URL sandbox/production;
- semántica de estados;
- reglas de expiración;
- comportamiento de refunds/chargebacks.

No copiar código de un proveedor como si fuera universal.
