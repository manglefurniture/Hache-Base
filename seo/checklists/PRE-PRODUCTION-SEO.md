# Checklist SEO preproducción

Usar en proyectos con `SEO_MODE=public` o `hybrid`.

## Bloqueantes

- [ ] `seo/baseline/MINIMUM-SEO-BASELINE.md`: todos los `MUST` aplicables están `PASS` o tienen excepción formal.
- [ ] No existe `Disallow: /` accidental en producción.
- [ ] No existe `noindex` accidental en rutas objetivo.
- [ ] Canonicals de producción apuntan al host/ruta correctos.
- [ ] Rutas inexistentes devuelven `404/410`, no una plantilla vacía con `200`.
- [ ] Sitemap contiene solo URLs deseadas, canónicas e indexables.
- [ ] Deep links públicos cargan directamente.
- [ ] Metadata crítica corresponde a cada ruta/plantilla.
- [ ] Schema, si existe, es sintácticamente válido y describe contenido visible real.
- [ ] Existe rollback para cambios de URLs, redirects, robots, canonicals y renderizado.

## Validación automática

```bash
SEO_MODE=public node seo/tests/seo-static.mjs <directorio-publico>
SEO_BASE_URL=https://example.com SEO_MODE=public bash seo/tests/seo-smoke.sh
```

## Validación humana mínima

- [ ] Intención y utilidad del contenido revisadas.
- [ ] Páginas locales representan ubicaciones/servicios reales y diferenciados.
- [ ] Claims sensibles/YMYL tienen revisión experta cuando aplica.
- [ ] Canonicals y redirects representan equivalencia real, no solo similitud técnica.
- [ ] Identidad, NAP, autores, fuentes y perfiles no se contradicen.

## Liberación

```text
GO: MUST aplicables PASS + smoke/CI verde.
NO-GO: MUST crítico/alto FAIL sin mitigación.
CONDITIONAL GO: WARNING documentado + responsable + monitor + fecha de corrección.
```
