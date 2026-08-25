# Reglas SEO automatizables

Una regla produce `PASS`, `WARNING`, `FAIL` o `N/A`. Nunca corrige automáticamente producción.

## Convención mínima

```text
ID: SEO-AREA-NNN
Estado: PASS | WARNING | FAIL | N/A
Severidad: CRÍTICA | ALTA | MEDIA | BAJA | EXPERIMENTAL
Evidencia: OFICIAL | EVIDENCIA FUERTE | EVIDENCIA MODERADA | EXPERIMENTO | CONSENSO PROFESIONAL | HIPÓTESIS | SIN EVIDENCIA SUFICIENTE
Alcance: URL | plantilla | directorio | sitio | entidad externa
```

## Reglas apropiadas para CI o smoke tests

| ID | Control | PASS / FAIL orientativo | Severidad | Evidencia | Automatización |
| --- | --- | --- | --- | --- | --- |
| SEO-SERVER-001 | HTTPS disponible | PASS: URL HTTPS responde; FAIL: TLS/conexión rota | CRÍTICA | OFICIAL | YES |
| SEO-SERVER-002 | Estado HTTP semántico | PASS: ruta esperada usa 200/3xx/404/410/5xx coherente; FAIL: shell/error con 200 | CRÍTICA | OFICIAL | PARTIAL |
| SEO-CRAWL-001 | `robots.txt` accesible | PASS: 200 y sintaxis básica; FAIL: inaccesible | ALTA | OFICIAL | YES |
| SEO-CRAWL-002 | Sin `Disallow: /` accidental en producción | PASS: no bloqueo global; FAIL: bloqueo global no autorizado | CRÍTICA | OFICIAL | YES |
| SEO-INDEX-001 | Sin `noindex` accidental en rutas objetivo | PASS: ausente; FAIL: presente donde se exige indexación | CRÍTICA | OFICIAL | YES |
| SEO-INDEX-002 | Canonical absoluta y única | PASS: una canonical HTTPS coherente; FAIL: ausente/duplicada/relativa según política | ALTA | OFICIAL | PARTIAL |
| SEO-SITEMAP-001 | Sitemap parseable | PASS: XML válido/URLs absolutas; FAIL: malformado | ALTA | OFICIAL | YES |
| SEO-ONPAGE-001 | `<title>` presente y no vacío | PASS: descriptivo no puede automatizarse; presencia sí | ALTA | OFICIAL | PARTIAL |
| SEO-ONPAGE-002 | Heading principal presente | PASS: existe contexto visible; calidad semántica requiere revisión | MEDIA | OFICIAL/CONSENSO | PARTIAL |
| SEO-JS-001 | Deep link devuelve documento utilizable | PASS: URL directa no cae en error/shell vacío | ALTA | OFICIAL | PARTIAL |
| SEO-MOBILE-001 | Viewport responsive | PASS: viewport adecuado; FAIL: ausente/configuración fija | ALTA | OFICIAL | YES |
| SEO-A11Y-001 | Imágenes con `alt` | PASS técnico: atributo presente; pertinencia requiere revisión | MEDIA | OFICIAL | PARTIAL |
| SEO-A11Y-002 | Inputs con nombre/label accesible | PASS técnico: label/aria-label/aria-labelledby; FAIL: control sin nombre | MEDIA | OFICIAL | YES |
| SEO-SCHEMA-001 | JSON-LD parseable | PASS: JSON válido; veracidad/tipo requiere revisión | ALTA | OFICIAL | PARTIAL |
| SEO-AI-001 | Política de bots deliberada | PASS: configuración revisada; FAIL: bloqueo accidental del bot objetivo | MEDIA | OFICIAL | PARTIAL |
| SEO-AI-002 | GPTBot separado de OAI-SearchBot | PASS: decisiones independientes cuando se configuran | MEDIA | OFICIAL | YES |
| SEO-AI-006 | `llms.txt` no tratado como requisito | PASS: experimental/opcional; FAIL: gate de producción por su ausencia | EXPERIMENTAL | OFICIAL | YES |

## Regla de interpretación

Estas pruebas detectan síntomas y regresiones. El informe debe agrupar fallos por causa raíz; por ejemplo, miles de URLs no canónicas en un sitemap son un problema del generador del sitemap, no miles de tareas aisladas.

## Política de CI

- Un `MUST` crítico/alto aplicable en `FAIL` debe bloquear la liberación o exigir excepción escrita.
- Un `WARNING` puede permitir liberación condicional si hay impacto acotado, monitor y fecha de corrección.
- Reglas `PARTIAL` solo automatizan la parte objetiva. No se debe inferir intención, calidad, equivalencia semántica o reputación a partir del test.
