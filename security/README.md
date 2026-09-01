# Security

Patrones de seguridad reutilizables de Hache-Base.

## Módulos incluidos

- `auth.php`: sesión segura, usuario requerido y cierre de sesión.
- `authorization.php`: permisos y aislamiento por sede/contexto.
- `csrf.php`: generación y validación de tokens CSRF.
- `bearer.php`: autenticación Bearer para APIs internas.
- `api-response.php`: respuestas JSON homogéneas, sin caché, códigos HTTP canónicos comunes y trazabilidad mediante `request_id`.
- `rate-limit.php`: limitador simple basado en sesión para flujos web autenticados.
- `headers.php`: cabeceras HTTP defensivas básicas.

Primitives relacionadas del Core:

- `src/common/RequestContext.php`: generación/normalización de `request_id` y `correlation_id`.
- `src/common/StructuredLogger.php`: logging JSON mínimo con campos estables y redacción recursiva de secretos.

La trazabilidad de cambios de negocio vive separada en `src/audit/` y `docs/AUDITORIA.md`; no se debe confundir auditoría histórica con logs operativos.

## Principios

1. Denegar por defecto.
2. Autorizar siempre en servidor.
3. Un ID válido no implica acceso permitido.
4. La sede/contexto autorizado proviene de la identidad autenticada.
5. Los secretos se cargan desde el entorno y nunca se versionan.
6. Las APIs internas usan autenticación explícita.
7. Las respuestas públicas no exponen excepciones, SQL, rutas o secretos.
8. La interfaz no sustituye controles de backend.
9. Los errores públicos usan códigos estables y mensajes seguros; los detalles técnicos viven en logs correlacionados.
10. IDs externos solo se propagan después de validación/normalización.

## Uso orientativo

```php
use HacheBase\Security\Auth;
use HacheBase\Security\Authorization;
use HacheBase\Security\Csrf;

$user = Auth::requireUser();
Authorization::requirePermission($user, 'clients.update');
Authorization::requireSite($user, $siteId);
Csrf::requireValid($_POST['_csrf'] ?? null);
```

Para una API interna:

```php
use HacheBase\Common\RequestContext;
use HacheBase\Security\Bearer;
use HacheBase\Security\ApiResponse;

Bearer::requireValid((string)getenv('INTERNAL_API_TOKEN'));
$context = RequestContext::fromServer();
ApiResponse::success(['status' => 'ok'], 200, $context);
```

Error HTTP de plataforma:

```php
ApiResponse::errorForStatus(404);
```

Error de dominio compatible con la API histórica:

```php
ApiResponse::error('ORDER_ALREADY_PAID', 'The order is already paid.', 409);
```

Logging mínimo:

```php
use HacheBase\Common\StructuredLogger;

$logger = new StructuredLogger('my-service', 'production', 'git-sha');
$logger->log('WARN', 'provider.retry', ['attempt' => 2], $context);
```

## Contrato de error

`ApiResponse` mantiene `json()`, `success()` y `error()` para consumidores existentes. Los payloads añaden `request_id` de forma aditiva y las respuestas emiten `X-Request-Id`/`X-Correlation-Id`.

Los estados canónicos de plataforma cubiertos por `errorForStatus()` son 400, 401, 403, 404, 409, 422, 429, 500 y 503. Los proyectos pueden usar códigos de dominio propios mediante `error()`, pero deben tratarlos como contrato estable una vez publicados.

## Límites

Estos archivos son una base reutilizable, no una garantía automática. Cada proyecto define su matriz real de permisos y amenazas.

`rate-limit.php` es deliberadamente simple y basado en sesión. Para APIs públicas o múltiples instancias se sustituye por almacenamiento compartido (Redis/DB) o un proxy/API gateway.

Las cabeceras también se adaptan al proyecto. Una Content-Security-Policy completa depende de los recursos reales utilizados y no debe inventarse desde una plantilla.

`StructuredLogger` no instala APM, tracing distribuido ni alertas. Es el schema mínimo para que un proyecto pueda adoptar esas Extensions después sin perder correlación básica.
