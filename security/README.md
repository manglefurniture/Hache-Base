# Security

Patrones de seguridad reutilizables de Hache-Base.

## Módulos incluidos

- `auth.php`: sesión segura, usuario requerido y cierre de sesión.
- `authorization.php`: permisos y aislamiento por sede/contexto.
- `csrf.php`: generación y validación de tokens CSRF.
- `bearer.php`: autenticación Bearer para APIs internas.
- `api-response.php`: respuestas JSON homogéneas, sin caché y sin exposición de detalles internos.
- `rate-limit.php`: limitador simple basado en sesión para flujos web autenticados.
- `headers.php`: cabeceras HTTP defensivas básicas.

La trazabilidad de cambios vive separada en `src/audit/` y `docs/AUDITORIA.md`.

## Principios

1. Denegar por defecto.
2. Autorizar siempre en servidor.
3. Un ID válido no implica acceso permitido.
4. La sede/contexto autorizado proviene de la identidad autenticada.
5. Los secretos se cargan desde el entorno y nunca se versionan.
6. Las APIs internas usan autenticación explícita.
7. Las respuestas públicas no exponen excepciones, SQL, rutas o secretos.
8. La interfaz no sustituye controles de backend.

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
use HacheBase\Security\Bearer;
use HacheBase\Security\ApiResponse;

Bearer::requireValid((string)getenv('INTERNAL_API_TOKEN'));
ApiResponse::success(['status' => 'ok']);
```

## Límites

Estos archivos son una base reutilizable, no una garantía automática. Cada proyecto define su matriz real de permisos y amenazas.

`rate-limit.php` es deliberadamente simple y basado en sesión. Para APIs públicas o múltiples instancias se sustituye por almacenamiento compartido (Redis/DB) o un proxy/API gateway.

Las cabeceras también se adaptan al proyecto. Una Content-Security-Policy completa depende de los recursos reales utilizados y no debe inventarse desde una plantilla.
