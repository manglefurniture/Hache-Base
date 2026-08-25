# Minimum SEO Baseline

Criterio portable de aceptación para webs nuevas. Derivado de `SEO Technical Base 2026`.

## Semántica

- `MUST`: bloquea producción salvo excepción escrita, con propietario, caducidad, mitigación y rollback.
- `SHOULD`: requiere justificación si se omite.
- `COULD`: opcional y medible.

## MUST

- [ ] DNS, HTTPS, certificado, redirección de host/protocolo y disponibilidad funcionan en producción.
- [ ] Producción no hereda autenticación, `Disallow: /`, `noindex` ni canonicals de staging.
- [ ] Cada URL pública responde con estado semántico correcto: `200`, `3xx`, `404/410` o `5xx`.
- [ ] URLs inexistentes no devuelven SPA/plantilla vacía con `200`.
- [ ] `/robots.txt` es accesible, válido y enlaza sitemaps pertinentes cuando aplica.
- [ ] Sitemap XML contiene solo URLs canónicas, `200` e indexables y respeta límites.
- [ ] Cada página objetivo es accesible mediante enlaces `<a href>` desde una ruta rastreable.
- [ ] Cada página objetivo tiene canonical única, absoluta, coherente y hacia una URL `200` indexable.
- [ ] Redirecciones no forman loops y los cambios permanentes llegan al equivalente final.
- [ ] Cada plantilla indexable entrega contenido principal y enlaces críticos en render comprobable.
- [ ] Deep links JavaScript cargan directamente; metadata, robots y canonical son correctos por ruta.
- [ ] Cada página indexable tiene `<title>` descriptivo, heading/contexto y contenido real para su intención.
- [ ] Imágenes informativas tienen alternativa; formularios tienen labels; navegación esencial funciona con teclado.
- [ ] Layout móvil, viewport, zoom, contenido, enlaces, metadata y schema mantienen paridad.
- [ ] Datos estructurados, si existen, son válidos, visibles, veraces y cumplen políticas aplicables.
- [ ] No se publican doorway pages, keyword stuffing, schema engañoso, contenido masivo sin valor ni enlaces manipulados.
- [ ] Sitio protege datos/administración, aplica parches y tiene monitor de uptime, 5xx, TLS y seguridad.
- [ ] GSC y Bing Webmaster Tools se verifican por propietarios autorizados cuando el proyecto tenga superficie pública relevante.
- [ ] Analytics/consentimiento, si se usan, funcionan sin bloquear contenido esencial y respetan normativa aplicable.
- [ ] Existe plan documentado de rollback para URLs, robots, canonicals, redirects y renderizado.

## SHOULD

- [ ] Arquitectura refleja servicios, temas y ubicaciones reales y evita huérfanas/facetas infinitas.
- [ ] Breadcrumbs visibles y `BreadcrumbList` coherente apoyan jerarquía donde aplica.
- [ ] Titles, descriptions, H1/contexto, anchors e imágenes se generan con controles por plantilla.
- [ ] Content briefs documentan audiencia, intención, evidencia, responsable y fecha de revisión.
- [ ] `Organization`, `LocalBusiness` y otros tipos soportados se implementan solo donde describen contenido real.
- [ ] Presupuesto de performance prueba plantillas críticas en móvil; CWV se monitoriza con campo cuando haya datos.
- [ ] Objetivo de campo: LCP p75 ≤ 2.5 s, INP p75 ≤ 200 ms y CLS p75 ≤ 0.10.
- [ ] Imágenes están dimensionadas, comprimidas, responsive y el recurso LCP se prioriza.
- [ ] Accesibilidad se prueba con herramientas y teclado/lector de pantalla en flujos críticos.
- [ ] Logs, releases y migraciones permiten correlacionar cambios con rastreo/visibilidad.
- [ ] GBP, si aplica, cumple elegibilidad, datos reales, categoría y horarios; no hay duplicados.
- [ ] Perfiles oficiales, NAP, nombre, logo y `sameAs` representan una entidad consistente.
- [ ] Política editorial contempla IA, revisión humana, fuentes, correcciones y contenido programático.
- [ ] Política de bots distingue búsqueda, entrenamiento, agentes y necesidades de negocio.
- [ ] Se define dashboard base de GSC/analytics/conversiones y responsables de alertas.

## COULD

- [ ] Añadir schema soportado adicional cuando habilite una presentación útil y sea mantenible.
- [ ] Crear feeds/APIs/datos estructurados adicionales para integraciones reales.
- [ ] Experimentar con `llms.txt` solo si existe consumidor identificado, hipótesis y medición.
- [ ] Medir citas/menciones en sistemas de IA separadas de clics y conversiones.
- [ ] Automatizar reglas `YES` en CI y muestreo `PARTIAL` en observabilidad.
- [ ] Ejecutar experimentos SEO controlados con hipótesis, ventana, guardrails y registro.

## Criterio de liberación

```text
GO: todos los MUST aplicables = PASS; excepciones firmadas con propietario, caducidad y rollback.
NO-GO: cualquier MUST CRÍTICO/ALTO = FAIL sin mitigación verificada.
CONDITIONAL GO: WARNING documentado, impacto acotado, monitor y fecha de corrección.
```
