# P1-02 — HTTP response fixture

P1-02 añade una prueba HTTP real y determinista sobre un servidor fixture local. Su objetivo es detectar drift entre los helpers de Hache Base y lo que finalmente sale por HTTP, sin confundir el fixture con evidencia de producción.

P1-06 reutiliza este mismo fixture para demostrar la **forma** de una matriz de caché de `PERF-011` y un drill de revalidación/invalidation. Los TTL concretos del fixture son ejemplos deterministas de prueba, no defaults universales para proyectos derivados.

## Qué verifica

`tests/http/ProductionReadinessHttpTest.sh` levanta temporalmente el servidor embebido de PHP con `tests/http/fixture-router.php` y comprueba mediante requests reales:

- headers defensivos de P0-07: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` y `Permissions-Policy`;
- CSP en modo `report-only` y ausencia simultánea de CSP enforce;
- ausencia de HSTS sobre el fixture HTTP cuando no existe opt-in HTTPS;
- cookie emitida con `HttpOnly`, `SameSite=Lax`, scope `/` y sin `Secure` sobre HTTP;
- políticas de caché públicas y privadas/no-store;
- P1-06: HTML público mutable con `no-cache` + `ETag`, incluyendo `304` cuando el validator sigue vigente y `200` con validator/cuerpo nuevo al cambiar la versión en el mismo URL;
- P1-06: asset con URL versionada/hashed marcado `public` + `immutable`, y asset no versionado sin `immutable`;
- P1-06: API pública con política pública explícita y HTML/API privada con `private, no-store, max-age=0`;
- P1-06: 404/500 continúan en `no-store` para evitar cachear fallos accidentalmente;
- negociación gzip con `Content-Encoding` y `Vary`, validando además el cuerpo comprimido;
- status 200/204/302/304/404/500;
- redirect y `Location` reales;
- cuerpos seguros para 404/500 sin stack traces ni paths internos.

## Qué NO demuestra

Un resultado verde del fixture no convierte automáticamente controles como SEC-001/002/003, PERF-011, ERR-001/004 o DPL-005 en PASS para un proyecto derivado. El proyecto real debe repetir las verificaciones contra su artefacto y entorno desplegado, incluyendo Nginx/Apache, CDN/proxy, TLS, compresión, caché, cookies y redirects reales.

El fixture de P1-06 tampoco demuestra que el string usado como ejemplo de asset versionado provenga del hash real del contenido de un build. Esa relación debe verificarse en el pipeline/artefacto del proyecto. La evidencia de `PERF-011` requiere además completar `templates/CACHE-POLICY.md` y probar la invalidación del proyecto real.

El fixture tampoco activa HSTS, no configura Cloudflare/Nginx, no sustituye smoke de producción y no adelanta controles futuros fuera del alcance del roadmap actual.

## Ejecución

```bash
bash tests/http/ProductionReadinessHttpTest.sh
```

La prueba está conectada a `tests/run.sh`, por lo que forma parte del CI normal de Hache Base.

## Adopción por proyecto

Para producir evidencia de proyecto, completar `templates/CACHE-POLICY.md` y reutilizar la matriz de checks apuntando a URLs desplegadas representativas. Registrar URL, commit/artefacto, entorno, fecha y salida.

Si una capa de infraestructura modifica headers, caché, compresión, cookies, redirects, validators o `Vary`, la respuesta final observada después de Nginx/CDN/proxy es la evidencia autoritativa. Los cambios de TTL/key/purge deben coordinarse con deploy y rollback; una política correcta solo en PHP no cierra `PERF-011`.
