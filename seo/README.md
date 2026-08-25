# Hache-Base SEO Module v1

Módulo reutilizable para incorporar SEO técnico desde arquitectura, desarrollo, CI y liberación, en lugar de añadirlo al final del proyecto.

## Fuente

El módulo deriva de `SEO Technical Base 2026`, investigación fechada el 24 de agosto de 2026. La base debe revisarse trimestralmente y después de cambios relevantes en Search Central, Search Console, Bing Webmaster Tools, Schema.org, Core Web Vitals o políticas de spam.

La copia maestra se conserva sin modificaciones en `reference/SEO-TECHNICAL-BASE-2026.md`. `reference/SOURCE-MANIFEST.md` registra SHA-256 y Git blob SHA; la copia versionada fue verificada byte a byte mediante coincidencia del blob Git con el archivo original recibido.

La fuente distingue claramente entre requisitos técnicos automatizables y decisiones que requieren juicio humano. Hache-Base conserva esa separación: una regla automática puede producir `PASS`, `WARNING`, `FAIL` o `N/A`, pero no debe realizar por sí sola cambios destructivos de SEO en producción.

## Modos de proyecto

Definir `SEO_MODE` al iniciar cada proyecto:

- `public`: sitio o rutas públicas cuyo objetivo incluye rastreo/indexación.
- `private-app`: panel/app autenticada; se evita indexación pública y solo aplican controles técnicos pertinentes.
- `hybrid`: mezcla de web pública indexable y aplicación privada.
- `none`: proyecto sin superficie web pública ni objetivo SEO.

## Flujo recomendado

Para proyectos `public` o `hybrid`:

`PRECHECK -> BACKUP -> TESTS -> SEO_BASELINE -> MIGRATIONS -> HEALTH -> DEPLOY_OK`

El orden exacto puede adaptarse al proyecto, pero ningún `MUST` crítico/alto debe llegar a producción con `FAIL` sin excepción documentada, propietario, mitigación y rollback.

## Contenido

- `reference/SEO-TECHNICAL-BASE-2026.md`: investigación maestra versionada e intacta.
- `reference/SOURCE-MANIFEST.md`: procedencia, vigencia y hashes de la investigación maestra.
- `baseline/MINIMUM-SEO-BASELINE.md`: criterio de aceptación MUST/SHOULD/COULD.
- `checklists/PRE-PRODUCTION-SEO.md`: gate operativo antes de liberar.
- `checklists/SEO-AUDIT-CHECKLIST.md`: formato reproducible de auditoría y hallazgos.
- `rules/AUTOMATABLE-RULES.md`: controles apropiados para CI/observabilidad.
- `rules/HUMAN-REVIEW-RULES.md`: decisiones que requieren validación humana.
- `tests/seo-static.mjs`: comprobaciones estáticas portables.
- `tests/seo-smoke.sh`: smoke tests contra una URL desplegada.
- `templates/robots.txt.example`: plantilla segura que debe adaptarse.
- `templates/sitemap-policy.md`: reglas para sitemaps.
- `templates/structured-data-policy.md`: política de schema.
- `REVIEW-STATUS.md`: estado de vigencia del módulo.

## Regla de seguridad

No desindexar, redirigir masivamente, borrar contenido, cambiar robots/canonicals, publicar schema/reseñas ni adquirir/desautorizar enlaces únicamente porque una regla automática falle. Primero exigir muestra, causa raíz, propietario, rollback y validación.
