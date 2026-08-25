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

## Principios

1. Denegar por defecto.
2. Autorizar siempre en servidor.
3. Un ID válido no implica acceso permitido.
4. La sede/contexto autorizado debe provenir de la identidad autenticada.
5. Los secretos se cargan desde variables de entorno y nunca se versionan.
6. Las APIs internas deben usar autenticación explícita.
7. Las respuestas de error públicas no deben exponer excepciones, SQL, rutas o secretos.
8. Los controles de interfaz no sustituyen controles de backend.

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

## Límites importantes

Estos archivos son una base reutilizable, no una garantía automática de seguridad. Cada proyecto debe definir su matriz real de permisos, modelo de sesión y amenazas.

El `rate-limit.php` incluido es deliberadamente simple y sirve para flujos de una sola instancia con sesión. Para APIs públicas, múltiples servidores o límites por IP/usuario a escala, debe sustituirse por almacenamiento compartido como Redis, base de datos o el mecanismo del proxy/API gateway.

Las cabeceras deben adaptarse al proyecto. En particular, una Content-Security-Policy completa depende de los recursos reales utilizados por cada aplicación y no debe inventarse desde la plantilla.

## Próxima capa

La auditoría de mutaciones (`audit_events`) se implementará como módulo separado para conservar trazabilidad administrativa y financiera sin acoplarla a autenticación.
