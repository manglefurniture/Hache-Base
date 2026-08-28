# Versionado seguro de credenciales de pago

Este patrón evita que un cambio de cuenta, token o secreto rompa pagos ya iniciados, devoluciones, contracargos o notificaciones tardías.

Aplica cuando una integración de pagos crea recursos externos que pueden seguir vivos después de rotar credenciales: preferencias, sesiones, intents, links, cargos, reembolsos o eventos equivalentes.

## Principio central

**Una credencial usada por una operación financiera no se sobreescribe. Se versiona.**

La configuración actual solo apunta a una versión. Cada operación local conserva la versión con la que nació.

## Invariantes obligatorias

1. **Versiones inmutables.** Cambiar token, secreto, ambiente, public key, cuenta, proveedor o referencia crea una fila nueva. No actualizar versiones históricas en sitio. La plantilla incluye un guard de base de datos que rechaza cualquier `UPDATE` sobre una versión de credenciales, incluso cuando ya no sea la versión actual.
2. **Vínculo operación → credencial.** El pedido, obligación o recurso local guarda `payment_credential_id` antes de crear el recurso externo.
3. **Rotación serializada.** Checkout toma lock compartido sobre la configuración mientras liga la operación a una versión; el cambio administrativo toma lock exclusivo (`FOR UPDATE` o equivalente).
4. **Retorno por versión.** La ruta de retorno/refresh consulta al proveedor con la credencial vinculada a esa operación, no con la credencial actual.
5. **Webhook histórico.** La firma se valida contra versiones históricas elegibles y, tras hacer match, la consulta autoritativa al proveedor usa el Access Token de esa misma versión.
6. **No mezclar firma y token.** Nunca validar con el secreto de una versión y consultar el pago con el token de otra.
7. **Versiones token-only solo para legado.** Si una instalación antigua tenía Access Token pero no Webhook Secret, preservar el token como versión histórica para retorno/consulta. Esa versión se excluye de candidatos de webhook y nunca puede quedar activa para nuevos checkouts.
8. **Activación estricta.** Una versión activa para nuevos pagos debe tener al menos el conjunto de secretos exigido por el proveedor; para un proveedor con webhook firmado: Access Token + Webhook Secret.
9. **Clave maestra fuera de BD.** Los secretos se cifran en reposo con una clave estable del servidor (`PAYMENT_GATEWAY_CONFIG_KEY` o equivalente). La clave no se guarda junto al ciphertext.
10. **AAD contextual obligatorio.** Cada ciphertext se autentica con `provider + credential_ref + propósito del campo`. Un token cifrado para una versión o columna no debe poder copiarse a otra y seguir autenticando.
11. **Referencia de versión inmutable.** `credential_ref` se genera antes de cifrar, se almacena junto a la versión y nunca se modifica. Debe ser única por proveedor.
12. **No rotar la clave maestra sin plan.** Cambiarla sin recifrar todas las versiones hace ilegibles las credenciales históricas.
13. **Historial retenido.** Una versión referenciada por operaciones no se borra. Usar FK con `ON DELETE RESTRICT` o una protección equivalente.
14. **Deshabilitar no borra historia.** Apagar la pasarela bloquea nuevos checkouts, pero no impide procesar webhooks, retornos, refunds o chargebacks de operaciones antiguas.

## Modelo mínimo

Usar la plantilla `database/modules/payment-gateway-credentials.sql` como referencia.

La estructura conceptual es:

- `payment_gateway_credentials`: versiones inmutables cifradas, con `credential_ref` opaca e inmutable;
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
      generar credential_ref inmutable
      cifrar el token legacy usando AAD de esa referencia y propósito
      crear versión histórica, incluso si no existe Webhook Secret
      ligar operaciones antiguas aún sin versión a esa credencial legacy

  calcular credenciales efectivas
  validar nueva cuenta/token contra el proveedor cuando exista endpoint de identidad
  exigir secretos necesarios si quedará activa
  generar credential_ref inmutable para la nueva versión
  cifrar cada secreto con AAD específico de su propósito
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
- cada versión legacy preservada recibe su propia `credential_ref` antes de cifrarse;
- después del takeover, la base de datos es autoritativa para la configuración de la pasarela;
- retirar variables legacy solo después de verificar que ninguna ruta depende directamente de ellas.

## Webhook con varias versiones

Proceso recomendado:

1. parsear firma y manifest exactamente como exige el proveedor;
2. obtener las versiones históricas retenidas;
3. omitir versiones sin Webhook Secret o sin token de consulta;
4. descifrar cada campo con el AAD de su `provider`, `credential_ref` y propósito exacto;
5. calcular HMAC/firma con cada secreto;
6. cuando una firma coincide, consultar el pago con el token de **esa misma versión**;
7. si varias versiones comparten secreto y el primer token no puede leer el pago, continuar con las demás versiones que compartan firma válida;
8. aplicar el pago local de forma idempotente y transaccional.

No limitar el webhook a la credencial actualmente activa.

## Retorno del comprador

Si la operación tiene `payment_credential_id`, resolver esa versión exacta y descifrar su token con el AAD de esa misma versión. Solo operaciones realmente legacy y aún no migradas pueden usar un fallback temporal.

Esto permite reconciliar un pago antiguo aunque la cuenta activa haya cambiado.

## Cifrado

`CredentialCipher.php` ofrece el sobre reutilizable AES-256-GCM. El proyecto debe inyectarle una clave estable del entorno y pasar contexto autenticado en cada operación.

`credential_ref` debe generarse **antes** de cifrar (UUID, ULID u otro identificador opaco estable) y almacenarse sin cambios en la fila de la versión. El propósito debe ser el nombre semántico estable del secreto, por ejemplo `access_token` o `webhook_secret`.

Ejemplo conceptual:

```php
$cipher = new CredentialCipher((string) env('PAYMENT_GATEWAY_CONFIG_KEY'));
$provider = 'PROVIDER_NAME';
$credentialRef = $generatedImmutableRef;

$encryptedToken = $cipher->encrypt(
    $accessToken,
    $provider,
    $credentialRef,
    'access_token'
);

$accessToken = $cipher->decrypt(
    $encryptedToken,
    $provider,
    $credentialRef,
    'access_token'
);
```

El AAD no se toma del propio ciphertext: se reconstruye desde metadatos inmutables de la versión. Si cambia proveedor, referencia o propósito, la autenticación GCM debe fallar. Por eso una versión persistida no se edita: cualquier cambio se modela creando otra versión y recifrando con su nuevo contexto.

Nunca renderizar de vuelta Access Tokens ni Webhook Secrets en inputs del panel. Un campo vacío al editar debe significar “conservar el secreto actual”, no “mostrarlo para editar”.

## Pruebas mínimas adicionales

Además de las pruebas generales de pagos:

- cifrado round-trip y rechazo de ciphertext alterado;
- rechazo de tag GCM truncado;
- rechazo de payload cifrado vacío;
- cambio de clave debe impedir descifrado;
- copiar un ciphertext a otra `credential_ref` debe fallar;
- copiar un ciphertext a otro propósito (`access_token` → `webhook_secret`) debe fallar;
- usar otro proveedor con el mismo ciphertext debe fallar;
- MariaDB debe rechazar un `UPDATE` sobre cualquier versión histórica, aunque no sea la vigente;
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

1. Añadir la tabla de versiones, `credential_ref` y el puntero de configuración.
2. Añadir el guard de base de datos que impide editar versiones históricas.
3. Añadir FK de versión a la tabla de dominio.
4. Definir una `PAYMENT_GATEWAY_CONFIG_KEY` aleatoria y estable en el servidor.
5. Implementar generación inmutable de `credential_ref` antes del cifrado.
6. Verificar el checkout legacy antes del primer takeover.
7. Ejecutar la primera transición preservando credenciales legacy.
8. Configurar credenciales nuevas desde el mecanismo administrativo.
9. Probar checkout en sandbox/test.
10. Probar webhook firmado real o sandbox.
11. Probar retorno con una operación ligada a una versión histórica.
12. No eliminar credenciales antiguas mientras existan operaciones que puedan generar eventos financieros posteriores.

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
