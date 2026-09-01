# Security

Patrones de seguridad reutilizables de Hache-Base.

## Módulos incluidos

- `auth.php`: frontera de autenticación/sesión, usuario requerido, login con rotación, elevación con rotación y logout.
- `session-security.php`: contrato P0-08 para cookies, idle/absolute expiry, fixation y destrucción efectiva.
- `request-security.php`: resolución compartida de HTTPS directo o detrás de proxy confiable, sin derivar IP de cliente.
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
13. Una sesión anónima no cruza a autenticada o privilegiada sin rotar su ID.
14. Logout significa invalidar estado servidor y cookie; una redirección visual no basta.

## Uso orientativo

```php
use HacheBase\Security\Auth;
use HacheBase\Security\Authorization;
use HacheBase\Security\Csrf;

$sessionConfig = [
    'idle_timeout' => 1800,
    'absolute_timeout' => 43200,
];

// Después de verificar credenciales:
Auth::login($user, $sessionConfig);

$user = Auth::requireUser($sessionConfig);
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

P0-07 y P0-08 comparten `RequestSecurity`: reconoce HTTPS directo mediante `HTTPS`, `REQUEST_SCHEME=https` o puerto 443 y **no confía en `X-Forwarded-Proto` por defecto**.

Si TLS termina antes de la aplicación, el proyecto declara IPs exactas del proxy:

```php
$proxy = [
    'trusted_ips' => ['10.0.0.5'],
    'forwarded_proto_header' => 'HTTP_X_FORWARDED_PROTO',
];
```

El `REMOTE_ADDR` observado por PHP debe coincidir exactamente con una IP configurada. El proxy confiable debe **sobrescribir/normalizar** el header de esquema a un único `https` o `http`; valores separados por coma se rechazan por ambigüedad. No se aceptan CIDR en este helper mínimo.

`RequestSecurity` decide únicamente HTTPS efectivo para headers/cookies. No redefine la IP del cliente, auditoría, identidad ni autorización.

## P0-08 — contrato de sesión

`Auth::startSecureSession()` sigue siendo source-compatible sin argumentos, pero ahora delega en `SessionSecurity` y aplica un contrato explícito de SEC-007.

Defaults del Core:

- `idle_timeout=1800` segundos;
- `absolute_timeout=43200` segundos;
- cookie de navegador de sesión (`lifetime=0`);
- `HttpOnly=true`;
- `SameSite=Lax`;
- cookie host-only (`cookie_domain=null`);
- `cookie_path=/` configurable;
- `Secure=true` solo cuando el request es HTTPS efectivo, incluyendo proxy confiable configurado;
- `session.use_strict_mode=1`, `session.use_only_cookies=1` y `session.use_trans_sid=0`.

Los valores de timeout/path/SameSite son baseline y deben revisarse por proyecto. `SameSite=None` exige HTTPS efectivo; el helper no permite crear una cookie `None` insegura.

### Login y elevación

Después de verificar credenciales:

```php
Auth::login($user, $sessionConfig);
```

`login()` regenera el ID antes de adjuntar `$_SESSION['user']` y reinicia la ventana absoluta de la nueva sesión autenticada.

Para una elevación ya autorizada:

```php
Auth::elevate($updatedUser, $sessionConfig);
```

`elevate()` exige una sesión autenticada, no permite cambiar de principal y regenera el ID. **No decide si el privilegio está autorizado**; esa decisión sigue perteneciendo a autorización/dominio.

Código histórico que asigna `$_SESSION['user']` directamente debe migrarse a `Auth::login()` para obtener protección contra fixation.

### Expiración

Cada request de sesión valida:

- inactividad `>= idle_timeout`;
- edad total `>= absolute_timeout`;
- metadata temporal regresiva/inconsistente.

Cuando expira, el estado autenticado se elimina y el ID rota a una sesión anónima nueva. La actividad renueva solo `last_seen_at`; una elevación no reinicia el límite absoluto original.

### Logout

`Auth::logout()` vacía `$_SESSION`, expira la cookie con los mismos atributos de scope/seguridad, destruye la sesión servidor e invalida el ID local. Si el servidor no puede destruir la sesión o expirar la cookie, el helper no finge éxito.

Completar `templates/SESSION-SECURITY.md` con cookies reales, login/elevación, expiración, logout y topología proxy antes de marcar SEC-007 como PASS.

## Evidencia de proyecto

Las primitives P0-07/P0-08 cubren parte reusable de SEC-001/002/003/007, pero no convierten controles en PASS. El proyecto debe comprobar headers/cookies reales por ruta, TLS/proxy real, inventario de subdominios, recursos CSP y sus CUF de autenticación. Usar `templates/SECURITY-HEADERS.md` y `templates/SESSION-SECURITY.md`.

## Límites

Estos archivos son una base reutilizable, no una garantía automática. Cada proyecto define su matriz real de permisos y amenazas.

P0-08 no implementa hashing de passwords, recuperación, MFA, enumeración, rate limit de login ni autorización. Esos controles pertenecen a SEC-008/009/010 y al proyecto.

`rate-limit.php` es deliberadamente simple y basado en sesión. Para APIs públicas o múltiples instancias se sustituye por almacenamiento compartido (Redis/DB) o un proxy/API gateway.

Una CSP completa depende de los recursos reales utilizados y no debe inventarse desde una plantilla. La transición report-only/enforce es responsabilidad del proyecto.

`StructuredLogger` no instala APM, tracing distribuido ni alertas. Es el schema mínimo para que un proyecto pueda adoptar esas Extensions después sin perder correlación básica.
