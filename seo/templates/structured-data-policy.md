# Política de datos estructurados

## Principios

Distinguir siempre:

1. schema sintácticamente válido;
2. tipo/propiedades soportados por el buscador objetivo;
3. elegibilidad para una presentación enriquecida.

La tercera nunca está garantizada por cumplir las dos primeras.

## Reglas

- Preferir JSON-LD cuando facilite mantenimiento, sin tratarlo como requisito universal.
- Marcar solo entidades, propiedades y relaciones que correspondan a contenido visible y real.
- No inventar precios, ratings, autores, fechas, ubicaciones, disponibilidad o identidad.
- `Organization`/`LocalBusiness`: mantener nombre, URL, logo, teléfono, dirección/área y perfiles coherentes.
- `sameAs`: solo identidades equivalentes; no usar como lista de backlinks.
- `BreadcrumbList`: debe coincidir con breadcrumbs/navegación visible cuando exista.
- `Review`/`AggregateRating`: no fabricar ni copiar puntuaciones externas de forma engañosa.
- `FAQPage`: no implementarlo esperando un rich result de Google en 2026; solo usar si semánticamente justificado.
- Schema válido pero no soportado no debe venderse como rich result.

## Validación

- Parsear JSON-LD en CI cuando sea posible.
- Validar vocabulario/sintaxis con herramientas de Schema.org.
- Validar tipos soportados con la herramienta oficial del buscador objetivo.
- Comparar markup contra contenido renderizado.
- Revalidar después de cambios de plantilla/documentación.

## Automatización segura

CI puede detectar JSON inválido, ausencia esperada o inconsistencias objetivas. No debe decidir automáticamente si una entidad, review, categoría o claim es auténtico.
