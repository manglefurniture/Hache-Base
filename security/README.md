# Security

Patrones de seguridad reutilizables de Hache-Base.

## Módulos incluidos

- `auth.php`: sesión segura, usuario requerido y cierre de sesión.
- `authorization.php`: permisos y aislamiento por sede/contexto.
- `csrf.php`: generación y validación de tokens CSRF.
- `bearer.php`: autenticación Bearer para APIs internas.
- `api-response.php`: respuestas JSON homogéneas, sin caché, códigos HTTP canónicos comunes y trazabilidad mediante `request_id`.
- `rate-limit.php`: limitador simple basado en sesión para flujos web autenticados.
- `headers.php`: baseline de headers defensivos + helper P0-07 configurable para CSP/HSTS y HTTPS detrás de proxy.

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
11. Un header persistente o restrictivo no se activa porque “parece seguro”: HSTS/CSP requieren evidencia del proyecto y rollout controlado.
12. Headers de proxy aportados por el cliente nunca se confían sin una frontera de proxy explícita.

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

## P0-07 — headers configurables

`Headers::apply()` conserva el uso histórico sin argumentos y emite únicamente el baseline no persistente:

- `X-Content-Type-Options: nosniff`;
- `X-Frame-Options: SAMEORIGIN` (o `DENY` si el proyecto lo configura);
- `Referrer-Policy: strict-origin-when-cross-origin`;
- `Permissions-Policy: geolocation=(), microphone=(), camera=()`.

`Headers::build()` devuelve el mismo mapa sin enviar headers y existe para pruebas, fixtures y validación previa al deploy.

Hache Base **no inventa una CSP universal** y **no activa HSTS por defecto**. Son controles de proyecto porque pueden romper CUF o persistir decisiones equivocadas en el navegador.

### CSP report-only → enforce

Configuración mínima de observación:

```php
use HacheBase\Security\Headers;

Headers::apply([
    'csp' => [
        'mode' => 'report-only',
        'directives' => [
            'default-src' => ["'self'"],
            'img-src' => ["'self'", 'https://images.example.test'],
            'report-uri' => ['/csp-report'],
        ],
    ],
]);
```

Modos admitidos:

- `off` — default; no se envía CSP;
- `report-only` — `Content-Security-Policy-Report-Only`;
- `enforce` — `Content-Security-Policy`.

Antes de `enforce`, completar `templates/SECURITY-HEADERS.md`: inventario real de recursos/orígenes, rutas/CUF, ventana de observación, violaciones legítimas, excepciones y rollback. Excepciones como `'unsafe-inline'`, `'unsafe-eval'`, comodines u orígenes amplios deben tener justificación y dueño.

`buildCspPolicy()` valida nombres de directiva y rechaza `;`, CR/LF y NUL en valores para evitar composición/inyección accidental de headers. Que una política sea sintácticamente segura **no demuestra que sea correcta para el proyecto**.

### HSTS explícito y reversible

HSTS se habilita solo después de confirmar HTTPS estable:

```php
Headers::apply([
    'hsts' => [
        'enabled' => true,
    ],
]);
```

Al activarse, el default es:

```text
Strict-Transport-Security: max-age=31536000
```

`includeSubDomains` y `preload` son `false` por default. Para habilitarlos se requiere configuración explícita; `preload=true` además exige HSTS activo, `includeSubDomains=true` y `max-age >= 31536000`. Esos checks solo validan coherencia técnica: el proyecto sigue obligado a inventariar y comprobar todos sus subdominios antes de adoptar esas opciones.

`max_age=0` está permitido como herramienta de retiro/rollback del estado HSTS donde corresponda.

### HTTPS detrás de proxy

El helper reconoce HTTPS directo mediante variables de servidor (`HTTPS`, `REQUEST_SCHEME=https` o puerto 443). **No confía en `X-Forwarded-Proto` por defecto.**

Si TLS termina antes de la aplicación, el proyecto puede declarar IPs exactas del proxy:

```php
Headers::apply([
    'hsts' => ['enabled' => true],
    'proxy' => [
        'trusted_ips' => ['10.0.0.5'],
        'forwarded_proto_header' => 'HTTP_X_FORWARDED_PROTO',
    ],
]);
```

El `REMOTE_ADDR` observado por PHP debe coincidir exactamente con una IP configurada. El proxy confiable debe **sobrescribir/normalizar** el header de esquema a un único `https` o `http`; valores separados por coma se rechazan por ambigüedad. No se aceptan CIDR en este helper mínimo.

Esta confianza de proxy sirve **solo** para decidir si HSTS puede emitirse en P0-07. No redefine identidad del cliente, IP de auditoría, cookies, sesión ni autenticación; esos aspectos pertenecen al contrato de sesión/trusted proxies de P0-08.

## Evidencia de proyecto

La primitive cubre parte reusable de SEC-001/SEC-002/SEC-003, pero no convierte ningún control en PASS. El proyecto debe comprobar headers reales por ruta, TLS/proxy real, inventario de subdominios, recursos CSP y CUF. Usar `templates/SECURITY-HEADERS.md` para esa evidencia.

## Límites

Estos archivos son una base reutilizable, no una garantía automática. Cada proyecto define su matriz real de permisos y amenazas.

`rate-limit.php` es deliberadamente simple y basado en sesión. Para APIs públicas o múltiples instancias se sustituye por almacenamiento compartido (Redis/DB) o un proxy/API gateway.

Una CSP completa depende de los recursos reales utilizados y no debe inventarse desde una plantilla. La transición report-only/enforce es responsabilidad del proyecto.

`StructuredLogger` no instala APM, tracing distribuido ni alertas. Es el schema mínimo para que un proyecto pueda adoptar esas Extensions después sin perder correlación básica.
