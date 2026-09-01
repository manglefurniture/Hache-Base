# SESSION SECURITY — PROJECT ADOPTION

> Plantilla P0-08 / SEC-007. Completar con el flujo real de autenticación, privilegios, proxy y cookies antes de declarar PASS. La primitive de Hache Base no sustituye las pruebas del proyecto desplegado.

## 1. Proyecto y alcance

- Proyecto: `<PROJECT>`
- Nivel Production Readiness: `B | C`
- Entorno: `<staging/production>`
- Rutas que crean/usan sesión: `<login, panel, etc.>`
- Rutas que elevan privilegios: `<...>`
- Dueño técnico: `<...>`
- Fecha/commit evaluado: `<...>`

## 2. Política de sesión

| Parámetro | Valor | Justificación |
| --- | --- | --- |
| Idle timeout | `<segundos>` | `<riesgo/UX>` |
| Absolute timeout | `<segundos>` | `<riesgo/UX>` |
| SameSite | `Lax | Strict | None` | `<flujo real>` |
| Cookie path | `<scope mínimo>` | `<rutas que necesitan sesión>` |
| Cookie domain | `<host-only/null o dominio explícito>` | `<por qué necesita compartir subdominio>` |
| HTTPS efectivo | `<directo/proxy>` | `<evidencia>` |

Hache Base usa por defecto `idle_timeout=1800`, `absolute_timeout=43200`, `SameSite=Lax`, cookie host-only y path `/`. Estos valores son baseline técnico, no decisión universal: cada proyecto debe revisar alcance y riesgo.

`SameSite=None` solo se permite sobre HTTPS efectivo para que la cookie pueda enviarse con `Secure`.

## 3. HTTPS y proxy confiable

La detección se comparte con P0-07 mediante `RequestSecurity`:

- HTTPS directo: `HTTPS`, `REQUEST_SCHEME=https` o puerto `443`;
- `X-Forwarded-Proto` no se confía desde un cliente arbitrario;
- solo se acepta desde una IP exacta incluida en `proxy.trusted_ips`;
- el proxy debe sobrescribir/normalizar el header a un único `https`/`http`;
- listas multi-hop separadas por coma se rechazan.

Config del proyecto:

```php
$sessionConfig = [
    'idle_timeout' => 1800,
    'absolute_timeout' => 43200,
    'same_site' => 'Lax',
    'cookie_path' => '/',
    'cookie_domain' => null,
    'proxy' => [
        'trusted_ips' => ['<PROXY_IP>'],
        'forwarded_proto_header' => 'HTTP_X_FORWARDED_PROTO',
    ],
];
```

Evidencia requerida:

- TLS termina en: `<...>`
- `REMOTE_ADDR` observado por PHP: `<...>`
- configuración del proxy que sobrescribe forwarded proto: `<...>`
- prueba de que un request no confiable con `X-Forwarded-Proto: https` no obtiene cookie Secure/HSTS por esa vía: `<...>`

## 4. Login y session fixation

Después de verificar credenciales, usar la frontera explícita:

```php
Auth::login($user, $sessionConfig);
```

El helper regenera el session ID **antes** de adjuntar el estado autenticado. No usar una sesión anónima preexistente como sesión autenticada sin rotación.

Registrar evidencia:

- session ID antes del login: `<hash/redacted evidence>`
- session ID después del login: `<distinto, sin guardar el valor real en logs>`
- test automatizado: `<...>`

No registrar cookies/session IDs reales como evidencia permanente.

## 5. Cambio/elevación de privilegios

Después de que la autorización real del proyecto apruebe el cambio:

```php
Auth::elevate($updatedUser, $sessionConfig);
```

`Auth::elevate()` **no autoriza** el privilegio: únicamente rota el session ID y reemplaza el estado autenticado ya aprobado. La autorización sigue en `authorization.php`/dominio del proyecto.

Evidencia:

- qué acción constituye elevación: `<...>`
- control que autoriza la elevación: `<...>`
- session ID rota al cruzar la frontera: `<test/evidencia>`

## 6. Expiración

La sesión expira cuando alcanza cualquiera de estos límites:

- inactividad `>= idle_timeout`;
- edad total `>= absolute_timeout`.

Al expirar, Hache Base elimina el estado autenticado y rota a una sesión anónima nueva. Un request con reloj temporal regresivo respecto a la metadata de sesión también invalida el estado de forma conservadora.

Probar al menos:

| Caso | Esperado | Evidencia |
| --- | --- | --- |
| Antes del idle timeout | usuario sigue autenticado | `<...>` |
| Exactamente en idle timeout | estado auth eliminado + ID rotado | `<...>` |
| Actividad dentro del idle | renueva `last_seen_at` | `<...>` |
| Exactamente en absolute timeout | estado auth eliminado + ID rotado | `<...>` |

## 7. Logout

Usar:

```php
Auth::logout($sessionConfig);
```

Si la configuración del proyecto cambió después de crear una sesión —por ejemplo un timeout, scope o IP de proxy nuevo durante un deploy— el logout **no debe quedar bloqueado por ese conflicto**. Hache Base persiste en la metadata de sesión el tuple efectivo de cookie que PHP quedó configurado para emitir (`path`, `domain`, `Secure`, `HttpOnly`, `SameSite`) y lo usa directamente para expirar la cookie durante logout, sin volver a deducirlo desde la topología de proxy actual. La configuración recibida por `logout()` queda como fallback para sesiones históricas sin ese snapshot.

El logout debe demostrar:

- `$_SESSION` vacía;
- sesión del servidor destruida;
- session ID local invalidado;
- cookie de sesión expirada con el mismo path/domain/security attributes aplicables;
- volver a una ruta protegida requiere autenticación nueva.

No considerar logout efectivo solo porque la UI redirigió a `/login`.

## 8. Cookies

Verificar en HTTPS real:

- `Secure=true`;
- `HttpOnly=true`;
- `SameSite` según el flujo;
- cookie host-only salvo necesidad explícita de dominio compartido;
- path mínimo compatible con las rutas que usan sesión;
- lifetime de cookie de navegador `0` (session cookie); la expiración auth del servidor se rige por idle/absolute timeout.

Si un proyecto necesita `SameSite=None`, dominio compartido o path `/`, justificar por CUF y comprobar CSRF/embeds/callbacks relacionados.

## 9. Migración de consumidores históricos

Código histórico que hace directamente:

```php
$_SESSION['user'] = $user;
```

debe migrarse a `Auth::login()` después de verificar credenciales. Para cambios de privilegio usar `Auth::elevate()`.

Hache Base debe iniciar la sesión **antes de cualquier `session_start()` histórico/framework**. Una sesión que ya esté activa antes de que `Auth` la gestione en ese request se rechaza de forma controlada antes de adjuntar autenticación, incluso si los flags de `php.ini` y `session_get_cookie_params()` parecen coincidir con la política candidata. Esos valores solo describen el runtime/emisión actual y no prueban los atributos `Path`/`Domain` de la cookie que llegó desde el navegador. Sin procedencia verificable independiente, adoptar esa sesión podría dejar una cookie antigua más específica capaz de sombrear la sesión autenticada.

Las sesiones que Hache Base abrió previamente **dentro del mismo request** sí conservan las migraciones anónimas controladas documentadas y probadas por P0-08, porque su procedencia y tuple efectivo están bajo el contrato de Hache Base.

Checklist de integración:

- buscar `session_start()` ejecutados antes de `Auth::startSecureSession()`/`Auth::login()`;
- mover el bootstrap de Hache Base antes de esos puntos; no basta con alinear después `session_set_cookie_params()`;
- probar explícitamente que cualquier sesión externa preactiva falla antes de completar login;
- no silenciar el `LogicException` y continuar adjuntando `$_SESSION['user']` manualmente.

`Auth::startSecureSession()`, `Auth::user()`, `Auth::requireUser()` y `Auth::logout()` mantienen llamadas sin argumentos compatibles, pero P0-08 introduce expiración explícita y puede cerrar sesiones antiguas al adoptar el nuevo contrato.

## 10. Evidencia SEC-007

| Control | Estado | Evidencia | Revisión humana | Notas |
| --- | --- | --- | --- | --- |
| Cookie Secure/HttpOnly/SameSite/scope | `PASS/FAIL/NOT EVALUATED` | `<HTTP evidence>` | `<persona/fecha>` | `<...>` |
| Regeneración login | `PASS/FAIL/NOT EVALUATED` | `<test>` | `<...>` | `<...>` |
| Regeneración elevación | `PASS/FAIL/NOT EVALUATED` | `<test>` | `<...>` | `<...>` |
| Idle/absolute expiry | `PASS/FAIL/NOT EVALUATED` | `<test>` | `<...>` | `<...>` |
| Logout efectivo | `PASS/FAIL/NOT EVALUATED` | `<test>` | `<...>` | `<...>` |
| Proxy HTTPS confiable | `PASS/FAIL/N/A/NOT EVALUATED` | `<config + test>` | `<...>` | `<...>` |

La disponibilidad de `SessionSecurity`/`Auth` en Hache Base **no convierte SEC-007 en PASS**. El proyecto debe probar su login, privilegios, cookies y proxy reales.
