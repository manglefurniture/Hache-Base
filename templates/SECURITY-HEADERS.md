# SECURITY HEADERS — PROJECT ADOPTION

> Plantilla P0-07. Completar con evidencia del proyecto real antes de promover CSP/HSTS. No copiar una política de otro proyecto sin inventariar sus recursos, subdominios y proxy/TLS.

## 1. Proyecto y alcance

- Proyecto: `<PROJECT>`
- Nivel Production Readiness: `A | B | C`
- Entorno evaluado: `<staging/production>`
- URLs/rutas representativas: `<...>`
- CUF afectados por headers/CSP: `<...>`
- Dueño técnico: `<...>`
- Fecha de revisión: `<YYYY-MM-DD>`

## 2. Inventario de recursos para CSP

Registrar solo orígenes realmente necesarios. Una entrada presente en el HTML no demuestra que deba permitirse si puede eliminarse.

| Recurso/tercero | Directiva CSP | Origen exacto | Rutas/CUF | Necesario | Fallback si falla | Dueño | Evidencia |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `<script principal>` | `script-src` | `'self'` | `<...>` | Sí | `<...>` | `<...>` | `<waterfall/test>` |
| `<imágenes>` | `img-src` | `<...>` | `<...>` | `<sí/no>` | `<...>` | `<...>` | `<...>` |
| `<API>` | `connect-src` | `<...>` | `<...>` | `<sí/no>` | `<...>` | `<...>` | `<...>` |

Excepciones como `'unsafe-inline'`, `'unsafe-eval'`, `*`, `data:` u orígenes amplios deben documentar causa, alcance, dueño y plan de retiro.

## 3. CSP — transición controlada

Estado actual: `off | report-only | enforce`

Política candidata:

```php
Headers::apply([
    'csp' => [
        'mode' => 'report-only',
        'directives' => [
            'default-src' => ["'self'"],
            // Añadir únicamente directivas/orígenes demostrados por el inventario.
        ],
    ],
]);
```

Antes de pasar de `report-only` a `enforce` registrar:

- ventana de observación: `<inicio/fin>`;
- rutas/CUF ejercitados: `<...>`;
- violaciones legítimas corregidas o allowlisted: `<...>`;
- falsos positivos/ruido conocido: `<...>`;
- prueba de teclado/formularios/login/pago/etc. cuando aplique: `<...>`;
- rollback: volver a `report-only` o `off` con commit/config identificable;
- aprobación humana: `<persona/fecha>`.

**No promover a `enforce` solo porque una navegación manual no produjo errores visibles.**

## 4. HTTPS, proxy y HSTS

### 4.1 Topología TLS/proxy

- Punto donde termina TLS: `<edge/load balancer/nginx/app>`
- IP que la app observa en `REMOTE_ADDR`: `<...>`
- Proxies confiables exactos: `<IP1, IP2...>`
- Header de esquema enviado por el proxy: `<HTTP_X_FORWARDED_PROTO u otro>`
- Evidencia de que el proxy **sobrescribe/normaliza** ese header a un único `https` o `http`: `<config/test>`
- Evidencia de que el cliente no puede inyectar/forjar ese valor hasta la app: `<config/test>`

Hache Base **no confía en `X-Forwarded-Proto` por defecto**. Solo se usa cuando `REMOTE_ADDR` pertenece a `proxy.trusted_ips` configurado explícitamente. Los valores separados por coma/multi-hop se rechazan: el proxy confiable debe entregar un único esquema autoritativo.

Ejemplo:

```php
Headers::apply([
    'proxy' => [
        'trusted_ips' => ['<PROXY_IP>'],
        'forwarded_proto_header' => 'HTTP_X_FORWARDED_PROTO',
    ],
]);
```

No añadir rangos o IPs por intuición. Si la infraestructura cambia, actualizar y volver a probar el contrato.

### 4.2 HSTS

HSTS queda **desactivado por defecto** porque una primitive no puede demostrar que el HTTPS del proyecto sea estable. Después de verificarlo se activa explícitamente. El valor base al activarlo es `max-age=31536000`, **sin** `includeSubDomains` y sin `preload`.

- HTTPS estable confirmado: `sí/no`
- `max_age` elegido: `<segundos>`
- Inventario de subdominios completado: `sí/no`
- Todos los subdominios sirven HTTPS válido y seguirán haciéndolo durante el max-age: `sí/no`
- `includeSubDomains` aprobado explícitamente: `sí/no`
- `preload` evaluado/aprobado explícitamente: `sí/no`
- Procedimiento de recuperación/impacto si un subdominio pierde HTTPS: `<...>`

Activación mínima después de confirmar HTTPS estable:

```php
Headers::apply([
    'hsts' => [
        'enabled' => true,
    ],
]);
```

Solo después de comprobar todos los subdominios:

```php
Headers::apply([
    'hsts' => [
        'enabled' => true,
        'include_subdomains' => true,
        // 'preload' => true, // decisión separada y explícita.
    ],
]);
```

`preload=true` exige HSTS habilitado, `includeSubDomains=true` y `max-age` mínimo de un año. El helper valida esas precondiciones, pero **no puede demostrar** que el inventario de subdominios sea correcto.

## 5. Headers baseline y anti-framing

Verificar en rutas representativas:

- `X-Content-Type-Options: nosniff`
- `Referrer-Policy`
- `Permissions-Policy`
- anti-framing mediante `X-Frame-Options: SAMEORIGIN|DENY` y/o `frame-ancestors` compatible cuando CSP esté en enforcement
- HSTS solo sobre HTTPS efectivo y solo después de activación explícita
- CSP report-only/enforced según el estado declarado

Si un proyecto necesita ser embebido cross-origin, no debilitar anti-framing sin threat model y evidencia específica.

## 6. Evidencia SEC-001 / SEC-002 / SEC-003

| Control | Estado | Evidencia | Revisión humana | Notas |
| --- | --- | --- | --- | --- |
| SEC-001 — HTTPS/HSTS/subdominios | `PASS/FAIL/N/A/NOT EVALUATED` | `<headers + inventario>` | `<persona/fecha>` | `<...>` |
| SEC-002 — nosniff/referrer/permissions/anti-framing | `PASS/FAIL/N/A/NOT EVALUATED` | `<headers por ruta>` | `<persona/fecha>` | `<...>` |
| SEC-003 — CSP específica, probada, excepciones documentadas | `PASS/FAIL/N/A/NOT EVALUATED` | `<policy/reportes/CUF>` | `<persona/fecha>` | `<...>` |

La disponibilidad de `security/headers.php` **no convierte estos controles en PASS**. El proyecto debe aportar evidencia del entorno real.
