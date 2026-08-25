# Política de sitemap

## Incluir

Solo URLs que el proyecto quiera presentar como candidatas preferidas y que sean, según la política del proyecto:

- canónicas;
- `200`;
- indexables;
- estables;
- relevantes para la superficie pública.

## No usar el sitemap para

- forzar indexación;
- incluir redirects, 404/410, `noindex` o duplicados subordinados;
- rotar URLs artificialmente para “forzar crawl budget”;
- publicar parámetros de tracking o IDs de sesión.

## `lastmod`

Actualizar cuando exista cambio significativo de contenido o datos relevantes. No cambiar fechas solo para simular frescura.

## Validación mínima

1. XML parseable.
2. URLs absolutas y del host esperado.
3. Muestreo de status HTTP.
4. Canonical consistente.
5. Sin `noindex` en URLs declaradas indexables.
6. Registrar y revisar el sitemap en herramientas del buscador cuando aplique.
