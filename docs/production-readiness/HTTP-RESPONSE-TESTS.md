# P1-02 — HTTP response fixture

P1-02 añade una prueba HTTP real y determinista sobre un servidor fixture local. Su objetivo es detectar drift entre los helpers de Hache Base y lo que finalmente sale por HTTP, sin confundir el fixture con evidencia de producción.

## Qué verifica

`tests/http/ProductionReadinessHttpTest.sh` levanta temporalmente el servidor embebido de PHP con `tests/http/fixture-router.php` y comprueba mediante requests reales:

- headers defensivos de P0-07: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` y `Permissions-Policy`;
- CSP en modo `report-only` y ausencia simultánea de CSP enforce;
- ausencia de HSTS sobre el fixture HTTP cuando no existe opt-in HTTPS;
- cookie emitida con `HttpOnly`, `SameSite=Lax`, scope `/` y sin `Secure` sobre HTTP;
- políticas de caché públicas y privadas/no-store;
- negociación gzip con `Content-Encoding` y `Vary`, validando además el cuerpo comprimido;
- status 200/204/302/404/500;
- redirect y `Location` reales;
- cuerpos seguros para 404/500 sin stack traces ni paths internos.

## Qué NO demuestra

Un resultado verde del fixture no convierte automáticamente controles como SEC-001/002/003, PERF-011, ERR-001/004 o DPL-005 en PASS para un proyecto derivado. El proyecto real debe repetir las verificaciones contra su artefacto y entorno desplegado, incluyendo Nginx/Apache, CDN/proxy, TLS, compresión, caché, cookies y redirects reales.

El fixture tampoco activa HSTS, no configura Cloudflare/Nginx, no sustituye smoke de producción y no adelanta P1-03 (Lighthouse/accesibilidad).

## Ejecución

```bash
bash tests/http/ProductionReadinessHttpTest.sh
```

La prueba está conectada a `tests/run.sh`, por lo que forma parte del CI normal de Hache Base.

## Adopción por proyecto

Para producir evidencia de proyecto, reutilizar la matriz de checks pero apuntar a URLs desplegadas representativas. Registrar URL, commit/artefacto, entorno, fecha y salida. Si una capa de infraestructura modifica headers, cache, compresión, cookies o redirects, esa salida final es la evidencia autoritativa para el proyecto.
