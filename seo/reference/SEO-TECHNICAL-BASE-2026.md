# SEO Technical Base 2026

> **Última investigación:** 24 de agosto de 2026  
> **Vigencia objetivo:** SEO 2026  
> **Revisión recomendada:** trimestral y después de cambios relevantes en Search Central, Search Console, Bing Webmaster Tools, Schema.org, Core Web Vitals o políticas de spam.

Este documento es un estándar técnico portable para auditoría, diseño, desarrollo y revisión SEO. Los sistemas de búsqueda cambian; una recomendación fechada no debe tratarse como verdad permanente.

## Índice

- [0. Cómo utilizar este documento](#0-cómo-utilizar-este-documento)
- [1. Principios fundamentales de SEO moderno](#1-principios-fundamentales-de-seo-moderno)
- [2. Rastreo](#2-rastreo)
- [3. Indexación](#3-indexación)
- [4. Arquitectura web](#4-arquitectura-web)
- [5. URLs](#5-urls)
- [6. SEO On-Page](#6-seo-on-page)
- [7. Contenido y calidad](#7-contenido-y-calidad)
- [8. SEO y contenido generado por IA](#8-seo-y-contenido-generado-por-ia)
- [9. JavaScript SEO](#9-javascript-seo)
- [10. Core Web Vitals y rendimiento](#10-core-web-vitals-y-rendimiento)
- [11. Mobile SEO](#11-mobile-seo)
- [12. Accesibilidad y SEO](#12-accesibilidad-y-seo)
- [13. Datos estructurados](#13-datos-estructurados)
- [14. SEO Local](#14-seo-local)
- [15. Backlinks y autoridad](#15-backlinks-y-autoridad)
- [16. Entidades y Knowledge Graph](#16-entidades-y-knowledge-graph)
- [17. SEO para buscadores y sistemas de IA](#17-seo-para-buscadores-y-sistemas-de-ia)
- [18. Visibilidad y citabilidad en IA](#18-visibilidad-y-citabilidad-en-ia)
- [19. llms.txt y tecnologías emergentes](#19-llmstxt-y-tecnologías-emergentes)
- [20. SEO para pequeñas empresas](#20-seo-para-pequeñas-empresas)
- [21. Herramientas](#21-herramientas)
- [22. Search Console](#22-search-console)
- [23. Mitos SEO que debemos dejar de repetir](#23-mitos-seo-que-debemos-dejar-de-repetir)
- [24. Errores que pueden destruir el SEO de un sitio](#24-errores-que-pueden-destruir-el-seo-de-un-sitio)
- [25. Matriz de prioridades](#25-matriz-de-prioridades)
- [26. Checklist técnico maestro](#26-checklist-técnico-maestro)
- [27. Reglas automatizables](#27-reglas-automatizables)
- [28. Qué NO debe automatizarse completamente](#28-qué-no-debe-automatizarse-completamente)
- [29. Minimum SEO Baseline](#29-minimum-seo-baseline)
- [30. SEO 2026: las 20 cosas que realmente importan](#30-seo-2026-las-20-cosas-que-realmente-importan)
- [31. Fuentes maestras](#31-fuentes-maestras)

---

## 0. Cómo utilizar este documento

### Propósito y alcance

Usar esta base para:

1. definir criterios de aceptación antes de producción;
2. ejecutar auditorías reproducibles;
3. priorizar por riesgo e impacto, no por cantidad de avisos;
4. convertir comprobaciones objetivas en pruebas automáticas;
5. reservar para revisión humana la intención, utilidad, reputación y contexto.

No es una lista de “factores secretos”, una garantía de indexación ni una receta universal. Cumplir requisitos técnicos hace una URL **elegible**; no obliga al buscador a rastrearla, indexarla, posicionarla ni mostrar un resultado enriquecido. [OFICIAL]

### Flujo de uso en auditoría

1. Inventariar tipos de URL y objetivos de negocio.
2. Resolver primero acceso, servidor, rastreo, renderizado e indexabilidad.
3. Comparar URL declarada, URL renderizada y versión indexada.
4. Segmentar hallazgos por plantilla, directorio y finalidad; no extrapolar una muestra sin comprobarla.
5. Asignar severidad, evidencia, alcance, esfuerzo y propietario.
6. Corregir una causa raíz antes que cientos de síntomas.
7. validar con crawler, pruebas de navegador, logs y Search Console; observar datos reales después del recrawl.

### Flujo de uso durante desarrollo

- Aplicar [Minimum SEO Baseline](#29-minimum-seo-baseline) como criterio de aceptación.
- Incorporar reglas `YES` de la [sección 27](#27-reglas-automatizables) a CI.
- Probar por plantilla y estado: éxito, vacío, error, sin resultados, paginación, filtro, autenticación y contenido cargado con JavaScript.
- Mantener mapas de redirección, canonicals, metadatos y schema como datos versionados y testeables.

### Severidades

| Severidad | Definición operativa | SLA orientativo |
|---|---|---|
| **CRÍTICA** | Impide o puede eliminar acceso, rastreo, renderizado, indexación o seguridad de una parte material del sitio. | Bloquear despliegue o corregir de inmediato. |
| **ALTA** | Puede causar pérdida considerable de visibilidad, consolidación, relevancia o tráfico cualificado. | Próximo ciclo; antes de campañas o migraciones. |
| **MEDIA** | Mejora relevante, acotada o dependiente del contexto. | Planificar tras resolver altas. |
| **BAJA** | Optimización incremental, estética o de mantenimiento. | Hacer cuando el coste sea bajo. |
| **EXPERIMENTAL** | Hipótesis o práctica emergente sin respaldo suficiente para convertirla en requisito. | Probar con medición y grupo de control. |

### Niveles de evidencia

| Etiqueta | Interpretación |
|---|---|
| `OFICIAL` | Documentación o declaración directa del motor/plataforma/estándar. Confirma política o capacidad, no siempre peso. |
| `EVIDENCIA FUERTE` | Experimento replicable, dataset amplio o convergencia de varias fuentes robustas. |
| `EVIDENCIA MODERADA` | Datos observacionales útiles con límites de muestra, mercado o causalidad. |
| `EXPERIMENTO` | Resultado bajo condiciones específicas; requiere replicación. |
| `CONSENSO PROFESIONAL` | Práctica ampliamente aceptada por especialistas, sin confirmación causal pública. |
| `HIPÓTESIS` | Explicación plausible aún no demostrada. |
| `SIN EVIDENCIA SUFICIENTE` | No debe venderse como factor, garantía o estándar. |

**Regla de interpretación:** una afirmación oficial de que algo “se usa” no revela su peso; una correlación de herramientas no demuestra que Google use esa métrica; una práctica que mejora UX puede ser valiosa sin ser ranking directo.

---

## 1. Principios fundamentales de SEO moderno

### La cadena de búsqueda

| Etapa | Qué sucede | Control del desarrollador |
|---|---|---|
| Descubrimiento/rastreo | El motor encuentra y solicita URLs mediante enlaces, sitemaps y señales externas. | Alto: enlaces, robots, sitemaps, servidor, estados HTTP. |
| Renderizado | Procesa HTML, CSS y JavaScript para obtener contenido y enlaces. | Alto: SSR/SSG, recursos accesibles, errores JS, latencia. |
| Indexación | Evalúa contenido, calidad, duplicación y elegibilidad para guardar una representación. | Medio-alto: indexabilidad, contenido, canonical, calidad; la decisión final es del motor. |
| Canonicalización | Agrupa duplicados y elige una URL representativa. | Medio: redirects y `rel=canonical` son señales fuertes; la elección final es del motor. |
| Recuperación | Para una consulta, recupera documentos candidatos y fragmentos relevantes. | Medio: claridad temática, entidades, texto accesible, enlaces. |
| Ranking | Ordena candidatos por relevancia, calidad, contexto, enlaces y otros sistemas. | Indirecto: optimizar señales; no controlar algoritmos ni peso. |
| Presentación | Genera título, snippet, rich results, mapas, módulos y respuestas de IA. | Medio: metadatos, controles de snippet, schema y feeds; no se garantiza visualización. |
| Calidad | Sistemas evalúan utilidad, fiabilidad y experiencia de manera multifactorial. | Medio: contenido y producto reales, mantenimiento, transparencia. |
| Anti-spam | Sistemas y acciones manuales neutralizan manipulación. | Alto para cumplimiento: evitar spam y proteger UGC/sitio. |

Google describe rastreo, indexación y serving como etapas distintas y no garantiza ninguna de ellas aun cumpliendo requisitos. [OFICIAL]([Google: How Search Works](https://developers.google.com/search/docs/fundamentals/how-search-works))

### Principios rectores

- **Elegibilidad antes que optimización:** una página inaccesible o no indexable no compite.
- **Consolidar antes que multiplicar:** una URL fuerte y diferenciada suele ser preferible a variantes débiles.
- **Relevancia antes que formato:** no existe longitud, número de headings o densidad universal.
- **Datos reales antes que puntuaciones aisladas:** Search Console, logs y CrUX prevalecen sobre una captura de laboratorio.
- **Usuarios antes que motores:** el contenido creado principalmente para manipular rankings puede violar políticas, aunque sea técnicamente impecable. [OFICIAL]
- **IA no sustituye fundamentos:** Google afirma en 2026 que AEO/GEO para sus experiencias generativas sigue siendo SEO; no exige markup especial. [OFICIAL]([Google: AI optimization guide](https://developers.google.com/search/docs/fundamentals/ai-optimization-guide))

---

## 2. Rastreo

| Tema | Qué es / riesgo | Diagnóstico | Recomendación | Evidencia | Prioridad |
|---|---|---|---|---|---|
| `robots.txt` | Control de solicitudes por crawler; no es seguridad ni garantía de desindexación. Un bloqueo global puede desaparecer contenido rastreable. | Solicitar `/robots.txt`, probar reglas por user-agent, comparar producción/staging, revisar logs. | Permitir recursos necesarios; usar autenticación para privado y `noindex` accesible para excluir de resultados. | `OFICIAL` [Google](https://developers.google.com/search/docs/crawling-indexing/robots/intro) | CRÍTICA |
| Meta robots | Directiva HTML por página. `noindex` accidental elimina URLs al recrawl. | Fuente y DOM renderizado; URL Inspection; crawler. | Plantillas indexables: sin `noindex`; entornos no públicos: autenticación además de directivas. | `OFICIAL` [Google](https://developers.google.com/search/docs/crawling-indexing/block-indexing) | CRÍTICA |
| `X-Robots-Tag` | Directiva HTTP útil para PDF y no-HTML; puede ser invisible al revisar solo el DOM. | `curl -I`, crawler con headers, URL Inspection. | Auditar cabeceras en HTML y assets; alinear con intención. | `OFICIAL` [Google](https://developers.google.com/search/docs/crawling-indexing/robots-meta-tag) | CRÍTICA |
| Crawlability | Capacidad de llegar y recibir contenido con éxito. WAF, CDN, DNS o 5xx pueden bloquear bots. | Logs, estados por user-agent, Search Console Crawl Stats/URL Inspection, pruebas desde redes externas. | Responder estable, no desafiar bots verificados, permitir CSS/JS críticos. | `OFICIAL` | CRÍTICA |
| Enlaces internos | Principal mecanismo de descubrimiento y contexto. Botones JS sin `href` pueden no ser rastreables. | Crawl desde home; inlinks; DOM renderizado; profundidad. | Usar `<a href>` con destino resoluble y anchor descriptivo. | `OFICIAL` [Google](https://developers.google.com/search/docs/crawling-indexing/links-crawlable) | ALTA |
| Sitemap XML | Lista de URLs preferidas; ayuda al descubrimiento, no garantiza rastreo/indexación. | Validar XML, estados, canonicals, fechas `lastmod`, reporte Sitemaps. | Incluir solo URLs canónicas, 200 e indexables; dividir cuando proceda; actualizar `lastmod` solo con cambios significativos. | `OFICIAL` [Google](https://developers.google.com/search/docs/crawling-indexing/sitemaps/overview) | ALTA |
| Códigos HTTP | Comunican éxito, ausencia, movimiento o fallo. `200` falso crea soft 404; 5xx sostenidos frenan rastreo. | Crawl, logs, monitor sintético, URL Inspection. | `200` solo con contenido válido; `301/308` permanente; `302/307` temporal; `404/410` ausente; `5xx` fallo real. | `OFICIAL` [Google](https://developers.google.com/search/docs/crawling-indexing/troubleshoot-crawling-errors) | CRÍTICA |
| Redirecciones | Trasladan usuarios y señales. Cadenas, loops y destinos irrelevantes añaden latencia o soft 404. | Seguir hops; mapa origen-destino; muestrear enlaces externos e internos. | Redirigir directo al equivalente final; actualizar enlaces y sitemap; evitar redirigir todo a home. | `OFICIAL` [Google](https://developers.google.com/search/docs/crawling-indexing/301-redirects) | ALTA |
| 404 / 410 | Respuestas válidas para recursos ausentes. No son “errores SEO” si la URL debe desaparecer. | Inlinks, tráfico, backlinks y equivalencia. | Mantener 404/410 si no hay reemplazo; 301 solo a equivalente útil; corregir enlaces internos rotos. | `OFICIAL` | MEDIA (contextual) |
| Soft 404 | `200` o redirect que representa ausencia, página vacía o error. | Contenido renderizado, Search Console, status real. | Retornar 404/410 o restaurar contenido; no redirigir masivamente a home. | `OFICIAL` | ALTA |
| Parámetros | Pueden multiplicar URLs de tracking, orden y filtros. | Agrupar por patrón; ratio únicas/duplicadas; logs. | Eliminar parámetros no funcionales de enlaces; canonical consistente; reglas de rastreo solo tras entender combinaciones. | `OFICIAL`/`CONSENSO PROFESIONAL` | ALTA en sitios grandes |
| Navegación facetada | Combinaciones de filtros pueden crear espacio infinito y duplicado. | Conteo de combinaciones, logs, crawl de patrones, indexación. | Definir facetas con demanda/valor indexable; bloquear o no enlazar combinaciones inútiles; canonicals coherentes. | `OFICIAL` | ALTA |
| Crawl traps | Calendarios infinitos, IDs de sesión, búsqueda interna, URLs generadas o paginación sin límite. | Crecimiento de URL, profundidad, logs y patrones repetitivos. | Límites deterministas, URLs estables, no enlazar espacios infinitos, controles en robots cuando corresponda. | `OFICIAL` | ALTA |
| Crawl budget | Capacidad y demanda de rastreo; relevante sobre todo en sitios grandes o con alta frecuencia de cambio. | Crawl Stats, logs, latencia, 5xx, duplicación y frescura. | No “optimizar presupuesto” en sitios pequeños sin evidencia; mejorar servidor y reducir espacios duplicados. | `OFICIAL` | MEDIA (solo sitios grandes/cambiantes) |

### Reglas de interacción críticas

```text
robots.txt bloquea rastreo; noindex requiere rastreo para ser visto.
URL bloqueada + noindex = Google puede no ver el noindex.
Sitemap = señal de descubrimiento/canonical débil; no orden de rastreo ni garantía.
Canonical = señal; no directiva absoluta.
```

> ⚠️ **OBSOLETO:** usar `noindex` dentro de `robots.txt`. Google no lo soporta.  
> ⚠️ **OBSOLETO:** rotar sitemaps o bloquear/desbloquear directorios para “forzar crawl budget”. Google lo desaconseja.  
> ⚠️ **OBSOLETO:** tratar cada 404 reportado como problema. Solo requiere acción si debía existir, tiene enlaces internos o posee un reemplazo equivalente.

---

## 3. Indexación

### Modelo de indexabilidad

Una URL candidata a indexación debería cumplir simultáneamente:

1. ser accesible al crawler;
2. responder con contenido útil y un estado apropiado;
3. no declarar `noindex`;
4. no ser un error, soft 404 o duplicado subordinado;
5. tener una canonical coherente;
6. aportar suficiente valor para que el motor decida indexarla.

### Problemas y tratamiento

| Problema | Diagnóstico | Acción | Evidencia | Prioridad |
|---|---|---|---|---|
| Canonical declarada distinta de la elegida | URL Inspection; comparar contenido, redirects, sitemap, enlaces y `rel=canonical`. | Alinear todas las señales; asegurar equivalencia real. No forzar canonical entre páginas diferentes. | `OFICIAL` [Google](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls) | ALTA |
| Duplicados | Hash/similitud, parámetros, protocolos, host, slash, impresión y filtros. | Elegir versión, redirigir si se retira la duplicada, canonical si debe permanecer accesible. | `OFICIAL` | ALTA |
| Thin content | Páginas sin respuesta sustancial o creadas solo para capturar variaciones. | Combinar, mejorar con valor propio, excluir o eliminar según finalidad. No usar umbral fijo de palabras. | `OFICIAL`/`CONSENSO PROFESIONAL` | ALTA |
| Página huérfana | Está en sitemap/analytics/logs pero sin enlaces internos rastreables. | Integrarla en la arquitectura si es importante; retirar si no tiene función. | `OFICIAL`/`CONSENSO PROFESIONAL` | ALTA |
| `Crawled – currently not indexed` | Google accedió pero no la incluyó; puede ser calidad, duplicación, estado transitorio o selección. | Inspeccionar muestra representativa; comparar canonical, contenido, internal links, render y logs. Mejorar el conjunto, no solicitar una por una masivamente. | `OFICIAL` con diagnóstico contextual | MEDIA–ALTA |
| `Discovered – currently not indexed` | URL conocida aún no rastreada; puede reflejar capacidad, prioridad, sobreproducción o sitio nuevo. | Mejorar enlaces, sitemaps y servidor; reducir URLs inútiles; esperar cuando sea reciente. | `OFICIAL` con diagnóstico contextual | MEDIA–ALTA |
| Sitemap con URL no indexable | Señales contradictorias. | Incluir únicamente 200, canonical e indexable que se quieran en resultados. | `OFICIAL` | ALTA |
| Indexación de búsqueda interna/filtros | Puede generar duplicación, baja calidad y crawl traps. | Evitar enlaces rastreables masivos; `noindex` o bloqueo contextual; crear landings curadas cuando exista demanda real. | `CONSENSO PROFESIONAL` | ALTA |

### Metodología con Search Console

1. En **Pages**, evaluar tendencias y tipos, no perseguir que “todas las URLs sean verdes”. Google indica que duplicados y URLs sin información útil no necesitan indexarse. [OFICIAL]([Page indexing report](https://support.google.com/webmasters/answer/7440203))
2. Segmentar por sitemap limpio para separar URLs deseadas de ruido.
3. Inspeccionar muestras de cada patrón: una URL afectada, una sana y una canonical relacionada.
4. Comparar **versión indexada** con **prueba en vivo**; la segunda prueba accesibilidad actual, no garantiza indexación ni considera todas las señales de calidad/seguridad.
5. Revisar HTML renderizado, screenshot, recursos, canonical declarada/elegida, fecha y crawler.
6. Cruzar con logs: descubierto no equivale a solicitado; solicitado no equivale a renderizado ni indexado.
7. Corregir plantilla/arquitectura y validar; esperar recrawl. Evitar solicitudes masivas de indexación.

---

## 4. Arquitectura web

### Objetivos

- Que cada URL importante tenga una función e intención claras.
- Que el usuario y el crawler lleguen mediante enlaces HTML.
- Que las relaciones jerárquicas y temáticas sean comprensibles.
- Que las categorías distribuyan navegación, contexto y autoridad sin crear duplicados.

### Patrones recomendados

**Negocio de servicios con ubicaciones reales**

```text
/
├── /servicios/
│   ├── /servicios/servicio-a/
│   └── /servicios/servicio-b/
├── /ubicaciones/
│   ├── /ubicaciones/ciudad-sucursal-1/
│   └── /ubicaciones/ciudad-sucursal-2/
├── /recursos/
│   └── /recursos/tema/
└── /contacto/
```

Las páginas locales deben corresponder a ubicaciones/servicios reales y contener información propia. Clonar una plantilla cambiando la ciudad puede constituir doorway abuse o contenido sin valor. [`OFICIAL`/`CONSENSO PROFESIONAL`]

**Sitio editorial o de conocimiento**

```text
/
├── /tema-a/                 ← hub/pilar
│   ├── /tema-a/subtema-1/
│   └── /tema-a/subtema-2/
└── /tema-b/
    └── /tema-b/subtema-1/
```

### Reglas prácticas

| Área | PASS | WARNING/FAIL |
|---|---|---|
| Jerarquía | La URL y breadcrumbs reflejan una relación útil. | Taxonomía creada solo por keywords. |
| Profundidad | Páginas importantes accesibles en pocos pasos razonables. | Umbral rígido de “máximo 3 clics” sin contexto; huérfanas sí es fallo. |
| Navegación | HTML estable y equivalente en móvil. | Menú solo tras interacción JS no rastreable. |
| Hubs | Agregan orientación, selección y contexto. | Página-lista sin contenido ni criterio. |
| Clusters | Cubren necesidades distintas enlazadas lógicamente. | Muchas páginas solapadas que canibalizan o repiten. |
| Breadcrumbs | Visibles, rastreables y coherentes; schema coincide. | Breadcrumb inventado solo en JSON-LD. |
| Paginación | Cada página tiene URL y enlaces secuenciales. | Scroll infinito sin URLs/enlaces alternativos. |

`topical authority` no es una métrica oficial pública. Construir cobertura coherente ayuda a usuarios, enlaces y comprensión, pero no existe evidencia pública de un umbral o puntaje universal. [CONSENSO PROFESIONAL]

---

## 5. URLs

| Práctica | Importancia | Regla |
|---|---|---|
| Estabilidad | Alta | No cambiar URLs sin beneficio y mapa de redirección. |
| Unicidad | Alta | Una intención/entidad principal por URL; evitar variantes técnicas. |
| Legibilidad | Media | Usar términos comprensibles, segmentos cortos y guiones. |
| Keywords | Media | Incluir palabras descriptivas naturales; no rellenar ni crear exact-match artificial. |
| Parámetros | Alta en escala | Mantener solo los que cambian función/contenido; evitar IDs de sesión y tracking en enlaces internos. |
| Minúsculas | Alta si servidor distingue | Normalizar; Google trata mayúsculas y minúsculas como URLs distintas. [OFICIAL] |
| Trailing slash | Técnica, no ranking | Elegir una política consistente y redirigir la otra si ambas resuelven. |
| Longitud | Preferencia | No existe límite SEO práctico universal; reducir complejidad y riesgo de truncado/errores. |
| Carpetas | Preferencia/contexto | Útiles para organización; no añaden autoridad por sí mismas. |
| Cambio | Alta | 301/308 directo a equivalente; actualizar links, canonical, sitemap, hreflang y feeds. |

Google recomienda guiones frente a guiones bajos, pocos parámetros y consistencia de mayúsculas. [OFICIAL]([URL structure](https://developers.google.com/search/docs/crawling-indexing/url-structure))

> ⚠️ **OBSOLETO:** reescribir URLs estables solo para hacerlas “más SEO”. El riesgo de migración puede superar una mejora estética.

---

## 6. SEO On-Page

### Función actual por elemento

| Elemento | Función principal | Nivel / notas |
|---|---|---|
| `<title>` | Comprensión, relevancia, CTR y fuente para title link | Señal directa/relevante `OFICIAL`; Google puede reescribirlo. Único, descriptivo, sin boilerplate excesivo. |
| H1 | Comprensión y UX | Relevancia/estructura. No existe regla oficial de exactamente uno; uno principal suele reducir ambigüedad. |
| H2–H6 | Comprensión, navegación y accesibilidad | Señal contextual/indirecta. Orden semántico importa más a accesibilidad que al ranking de Google. |
| Meta description | CTR/presentación | No ranking directo confirmado; Google puede elegir texto de la página. Describir valor e intención sin longitud rígida. |
| Contenido principal | Relevancia, calidad, satisfacción | Fundamental. Debe responder la intención con información verificable y diferenciada. |
| Imágenes | Comprensión multimodal, Image Search, UX | Filename, contexto, dimensiones, calidad y alt cuando corresponda. |
| `alt` | Accesibilidad y comprensión de imagen | Importante; vacío para decorativas, descriptivo para informativas; evitar stuffing. |
| Anchor text | Descubrimiento y contexto | Google confirma uso de enlaces para descubrimiento y relevancia. Natural y descriptivo. |
| Multimedia | Utilidad y superficies adicionales | Indirecto; acompañar con texto, captions/transcripción cuando aporta. |
| Enlaces internos | Descubrimiento, contexto y distribución interna | Directamente operativos para crawling; no fijar cantidad universal. |
| Enlaces externos | Evidencia y utilidad | No hay “bonus” automático por enlazar; usar fuentes fiables. Calificar enlaces pagados/UGC. |
| Tablas | Comprensión y comparación | Formato útil, no factor directo confirmado. Usar headers/caption accesibles. |
| Listas | Escaneabilidad y estructura | UX/comprensión; no garantía de featured snippet o IA. |
| FAQs visibles | Utilidad para preguntas reales | Útiles por contenido; el rich result de FAQ dejó de aparecer en Google el 7 de mayo de 2026. |
| Entidades | Desambiguación y relaciones | Comprensión; coherencia factual y enlaces/perfiles oficiales. No “densidad de entidades”. |
| Intención | Adecuación a la necesidad | Concepto central de relevancia; requiere juicio humano y análisis de resultados/usuarios. |

Fuentes: [Search Essentials](https://developers.google.com/search/docs/essentials), [title links](https://developers.google.com/search/docs/appearance/title-link), [snippets](https://developers.google.com/search/docs/appearance/snippet), [image SEO](https://developers.google.com/search/docs/appearance/google-images).

### Criterios de calidad de title y headings

- `title`: específico, fiel al contenido, distintivo dentro del sitio y entendible fuera de contexto.
- H1: título visible que confirma la tarea o tema principal.
- Subheadings: describen secciones; no insertar keywords si no ayudan.
- No ocultar headings ni usar jerarquía solo para tamaño visual.

> ⚠️ **OBSOLETO:** meta keywords. Google declara que no las usa para indexación ni ranking.  
> ⚠️ **OBSOLETO:** densidad exacta de keywords. No existe porcentaje óptimo oficial; la repetición artificial puede ser spam.

---

## 7. Contenido y calidad

### Qué está confirmado

- Los sistemas buscan priorizar contenido útil, fiable y creado para personas. [OFICIAL]
- Las guías de evaluadores ayudan a evaluar sistemas; los evaluadores no cambian rankings directamente. [OFICIAL]
- Google integró el antiguo sistema de helpful content en sistemas principales multifactoriales en 2024; no existe ya un único “Helpful Content System” aislado. [OFICIAL]
- Experiencia directa, autoría clara, fuentes, exactitud y transparencia pueden ayudar a demostrar confianza; no existe una puntuación pública de E-E-A-T. [OFICIAL]
- En temas YMYL (salud, finanzas, seguridad, civismo), la fiabilidad exige mayor rigor. [OFICIAL]

### E-E-A-T: qué sabemos y qué no

| Afirmación | Veredicto | Evidencia |
|---|---|---|
| E-E-A-T aparece en las Quality Rater Guidelines. | Confirmado. | `OFICIAL` |
| Los raters asignan rankings a páginas. | Falso. | `OFICIAL` |
| E-E-A-T es un único factor o score medible. | Falso/no confirmado; Google dice que no es un factor individual. | `OFICIAL` [SEO Starter Guide](https://developers.google.com/search/docs/fundamentals/seo-starter-guide) |
| Señales automatizadas pueden alinearse con aspectos de E-E-A-T. | Confirmado en términos generales; señales y pesos no son públicos. | `OFICIAL` |
| Agregar una bio por sí sola sube rankings. | Sin evidencia causal suficiente. | `SIN EVIDENCIA SUFICIENTE` |
| Experiencia demostrable mejora utilidad y confianza. | Fuerte como criterio de calidad; peso de ranking no aislado. | `OFICIAL`/`CONSENSO PROFESIONAL` |

### Evaluación humana mínima

Preguntar:

- **Quién:** ¿autor/organización identificables y adecuados? ¿conflictos y contacto claros?
- **Cómo:** ¿método, fuentes, pruebas, fecha y límites explicados?
- **Por qué:** ¿se creó para ayudar a una audiencia real o para capturar tráfico?
- ¿Aporta experiencia, datos, ejemplos o análisis no intercambiables?
- ¿Resuelve la tarea sin obligar a buscar de nuevo lo esencial?
- ¿Está actualizado donde la vigencia importa?
- ¿Diferencia hechos, estimaciones y opiniones?

### Riesgos de sobreoptimización

- Keyword stuffing en texto, titles, anchors y alt.
- Páginas programáticas que cambian solo entidad/ciudad.
- Introducciones largas para alcanzar palabras.
- FAQs inventadas para cubrir variaciones de consultas.
- Schema con contenido invisible o ratings propios abusivos.
- Actualizar fechas sin cambios sustantivos.
- Producir volumen que el equipo no puede revisar ni mantener.

Fuente principal: [Google: helpful, reliable, people-first content](https://developers.google.com/search/docs/fundamentals/creating-helpful-content).

---

## 8. SEO y contenido generado por IA

### Postura actual

Google no penaliza automáticamente el uso de IA; evalúa el propósito y el resultado. La generación masiva sin valor puede caer en **scaled content abuse**, independientemente de si la produce una persona, un modelo o ambos. [OFICIAL]([Guidance on generative AI content](https://developers.google.com/search/docs/fundamentals/using-gen-ai-content), [Spam policies](https://developers.google.com/search/docs/essentials/spam-policies))

| Uso | Riesgo | Control requerido |
|---|---|---|
| Borrador asistido y revisado por experto | Bajo–medio | Verificación factual, edición, fuentes, valor propio. |
| Resumen de material propio | Bajo | Comprobar pérdida de contexto, atribución y actualización. |
| Traducción automática | Medio | Revisión nativa; evitar publicar miles de páginas sin demanda/calidad. |
| Fichas programáticas con datos únicos y útiles | Medio | Datos fiables, plantilla con valor, QA por muestras y retirada de vacíos. |
| Miles de páginas reescritas de fuentes ajenas | Alto | No publicar; puede ser scraping/scaled content abuse. |
| IA sin revisión en YMYL | Crítico | Revisión experta obligatoria, fuentes primarias, responsabilidad editorial. |
| Metadatos/alt/schema generados | Medio | Validación contra contenido visible; evitar alucinaciones. |

### Criterio de publicación

```text
PASS = exacto + útil + original/aporta valor + revisado + atribuible + mantenible
FAIL = escala > capacidad de QA, inventa hechos, imita sin aportar o existe solo para manipular búsqueda
```

Revelar el uso de automatización cuando ayude al usuario a entender el proceso o sea material para la confianza. No existe obligación SEO universal de etiquetar cada asistencia de IA. [`OFICIAL`; depende del contexto]

---

## 9. JavaScript SEO

### Modelos de renderizado

| Modelo | Ventaja SEO | Riesgo | Uso recomendado |
|---|---|---|---|
| SSG | HTML completo, rápido y cacheable. | Rebuild/frescura en gran escala. | Contenido estable, marketing, docs. |
| SSR | HTML por solicitud, metadatos por URL. | TTFB, coste y fallos de servidor. | Contenido dinámico indexable. |
| ISR/revalidación | Equilibrio entre frescura y caché. | Inconsistencias durante regeneración. | Catálogos/editorial con cambios. |
| CSR | App rica en cliente. | Contenido tardío, fallos de JS, segunda fase de render, metadatos/rutas débiles. | Áreas autenticadas o cuando indexación no sea objetivo. |
| Prerender | HTML anticipado. | Obsolescencia, divergencia. | Solución controlada cuando SSR/SSG no es viable. |
| Dynamic rendering | Sirve versión diferente a bots. | Complejidad y posible divergencia. Google lo considera workaround, no solución recomendada. | Solo legado temporal con equivalencia estricta. |

### Requisitos para aplicaciones modernas

- Cada vista indexable debe tener URL estable y devolver contenido principal y metadata correctos por URL.
- Preferir SSR/SSG/ISR para contenido crítico. CSR puede indexarse en Google, pero aumenta complejidad y dependencia del render. [OFICIAL]
- Enlaces de navegación: `<a href="/ruta">`; no depender de `onclick`, fragments o estados internos.
- Routing SPA: servidor debe resolver deep links; errores deben retornar 404, no shell `200` genérico.
- `title`, description, canonical, robots, hreflang y schema deben corresponder a la ruta, idealmente en HTML inicial.
- No cambiar canonical con JavaScript si ya existe en HTML. [OFICIAL]
- Lazy loading: no exigir scroll/click para cargar contenido o imágenes que deban indexarse; usar APIs observables y fallbacks.
- Hydration: evitar contenido principal en blanco, mismatch y reemplazo de metadata.
- No bloquear bundles, APIs o CSS necesarios para renderizar; proteger datos privados en origen, no con robots.
- Probar fuente, DOM renderizado y HTML de URL Inspection; comparar visual y texto.

Fuente: [JavaScript SEO basics](https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics), [fix JavaScript problems](https://developers.google.com/search/docs/crawling-indexing/javascript/fix-search-javascript), [dynamic rendering](https://developers.google.com/search/docs/crawling-indexing/javascript/dynamic-rendering).

---

## 10. Core Web Vitals y rendimiento

### Umbrales vigentes

Medir al percentil 75, separado por móvil y escritorio.

| Métrica | Buena | Necesita mejora | Mala | Rol |
|---|---:|---:|---:|---|
| LCP | ≤ 2.5 s | > 2.5–4.0 s | > 4.0 s | Core Web Vital: carga del contenido principal. |
| INP | ≤ 200 ms | > 200–500 ms | > 500 ms | Core Web Vital: respuesta a interacciones. |
| CLS | ≤ 0.10 | > 0.10–0.25 | > 0.25 | Core Web Vital: estabilidad visual. |
| TTFB | ≤ 0.8 s orientativo | > 0.8–1.8 s | > 1.8 s | Diagnóstico; no CWV. |
| FCP | ≤ 1.8 s | > 1.8–3.0 s | > 3.0 s | Diagnóstico; no CWV. |

Fuentes: [Web Vitals](https://web.dev/articles/vitals), [threshold methodology](https://web.dev/articles/defining-core-web-vitals-thresholds), [TTFB](https://web.dev/articles/ttfb), [FCP](https://web.dev/articles/fcp).

### Laboratorio vs. campo

| Datos | Qué representan | Herramientas | Decisión |
|---|---|---|---|
| Laboratorio | Ejecución sintética controlada; reproducible, útil para diagnosticar y evitar regresiones. | Lighthouse, DevTools, CI. | Encontrar causa y comparar builds. No declarar experiencia real universal. |
| Campo | Experiencias reales con dispositivos, redes, ubicaciones e interacciones reales. | CrUX, Search Console CWV, RUM. | Evaluar impacto y cumplimiento real. |

CrUX usa datos agregados de Chrome durante 28 días y p75; PSI combina CrUX (si hay muestra suficiente) con Lighthouse. Lighthouse no mide INP real sin usuarios y usa TBT como proxy de laboratorio. [OFICIAL]([CrUX API](https://developer.chrome.com/docs/crux/api), [PSI](https://developers.google.com/speed/docs/insights/v5/about), [lab vs field](https://web.dev/articles/lab-and-field-data-differences))

### Peso SEO real

Google confirma que CWV se usa en sus sistemas, pero la relevancia puede prevalecer y un puntaje perfecto no garantiza primeras posiciones. No existe un único “page experience signal”; mejorar para usuarios y conversiones suele tener más valor que perseguir 100/100. [OFICIAL]([Page experience](https://developers.google.com/search/docs/appearance/page-experience))

### Recomendaciones técnicas

| Objetivo | Acciones prioritarias |
|---|---|
| LCP | Optimizar TTFB; servir HTML temprano; identificar recurso LCP; no lazy-load del hero; `preload`/prioridad con criterio; formatos/tamaños adecuados; reducir recursos bloqueantes. |
| INP | Reducir tareas largas; dividir trabajo; bajar JS; evitar handlers costosos; renderizar actualizaciones pequeñas; medir interacciones reales y contexto. |
| CLS | Reservar dimensiones/aspect-ratio; espacios para ads/embeds; evitar insertar arriba; estabilizar fuentes; animar con transform cuando proceda. |
| TTFB | Caché, CDN, queries/backend, redirects, compresión, conexión y capacidad. |
| FCP | CSS crítico, fuentes, HTML, recursos bloqueantes, caché y TTFB. |

Definir presupuestos por plantilla y monitorizar regresiones en CI, pero decidir con campo/RUM después de producción.

---

## 11. Mobile SEO

Google usa la versión móvil del contenido para indexación y ranking. No tener versión móvil no excluye automáticamente, pero es fuertemente desaconsejado. [OFICIAL]([Mobile-first indexing](https://developers.google.com/search/docs/crawling-indexing/mobile/mobile-sites-mobile-first-indexing))

### Baseline móvil

- Diseño responsive preferido por simplicidad; URLs móviles separadas requieren canonicals/alternates y paridad estricta.
- Mismo contenido principal, title, description, robots, headings, alt y structured data en móvil y escritorio.
- Menús, accordions y tabs son válidos si el contenido existe y es accesible; ocultarlo para simplificar móvil puede reducir información indexable.
- Viewport configurado; no scroll horizontal involuntario.
- Targets táctiles espaciados y controles con nombre accesible.
- Texto legible sin zoom; formularios con tipos de input apropiados.
- Imágenes responsive (`srcset`/`sizes`), dimensiones reservadas y hero priorizado.
- Interstitials no intrusivos; contenido principal distinguible.
- Probar en dispositivos de gama baja, red móvil y estados de teclado/orientación.

**No confundir:** mobile-first indexing es selección de contenido para indexar; responsive design es una implementación; “mobile friendly” es calidad de experiencia.

---

## 12. Accesibilidad y SEO

Accesibilidad y SEO se solapan porque ambos se benefician de contenido comprensible y navegación robusta, pero cumplir WCAG no es un factor de ranking directo confirmado. [`OFICIAL`/`CONSENSO PROFESIONAL`]

| Área | Beneficio de accesibilidad | Relación SEO |
|---|---|---|
| HTML semántico | Roles y estructura nativos. | Facilita parsing, mantenimiento y agentes; Google tolera HTML imperfecto. Indirecta. |
| Headings | Navegación por secciones. | Contexto y estructura; orden no es factor rígido de Google. |
| `alt` | Alternativa para imágenes. | Comprensión e Image Search; directo para imagen/contexto, no pretexto para keywords. |
| Labels | Nombre de controles. | UX/conversión; agentes pueden interpretar acciones. Sin ranking directo confirmado. |
| Landmarks | Navegación por regiones. | Comprensión de interfaz y agentes; indirecta. |
| Enlaces/teclado | Operabilidad sin mouse. | Reduce rutas inaccesibles; enlaces HTML también mejoran crawling. |
| Contraste | Legibilidad. | UX; no factor directo público. |
| ARIA | Expone nombre, rol y estado cuando HTML no basta. | Agentes y accesibilidad; ARIA incorrecto empeora la interfaz. |

### Reglas

- Usar elementos nativos antes de recrearlos con `div` + ARIA.
- `alt=""` en decorativas; descripción equivalente en informativas; no repetir captions sin necesidad.
- Asociar `label` a inputs; mensajes de error anunciables y accionables.
- Mantener foco visible, orden lógico y bypass al contenido.
- Aplicar WCAG 2.2 según obligación legal/objetivo, no solo la auditoría automática.
- Combinar pruebas automáticas con teclado y lector de pantalla; los tests no detectan toda la calidad semántica.

Fuentes: [W3C WCAG 2.2 Quick Reference](https://www.w3.org/WAI/WCAG22/quickref/), [WAI headings](https://www.w3.org/WAI/tutorials/page-structure/headings/), [web.dev agent-friendly sites](https://web.dev/articles/ai-agent-site-ux).

---

## 13. Datos estructurados

### Tres capas que no deben confundirse

1. **Schema válido:** vocabulario y sintaxis aceptados por Schema.org Validator.
2. **Schema soportado por Google:** tipo/propiedades documentados en Search Gallery.
3. **Elegible para rich result:** cumple requisitos técnicos, de contenido y políticas. La visualización nunca está garantizada.

Google recomienda JSON-LD por mantenimiento, aunque también acepta Microdata y RDFa. El markup debe describir contenido visible y real; una acción manual de structured data puede retirar la elegibilidad del rich result sin necesariamente afectar el ranking web ordinario. [OFICIAL]([Structured data intro](https://developers.google.com/search/docs/appearance/structured-data/intro-structured-data), [policies](https://developers.google.com/search/docs/appearance/structured-data/sd-policies))

### Matriz de tipos

| Tipo | Cuándo usar | Propiedades importantes | Rich result / soporte Google | No usar / errores comunes |
|---|---|---|---|---|
| `Organization` | Identidad de organización, normalmente home/About. | `name`, `url`, `logo`, `sameAs`, contacto, dirección cuando aplique. | Información de organización/knowledge panels; soportado. | Repetir grafos contradictorios en cada página; inventar IDs/perfiles. |
| `LocalBusiness` | Ubicación física elegible o negocio local real. Usar subtipo específico. | `name`, `address`, `telephone`, `url`, `openingHoursSpecification`, `geo`; propiedades Google vigentes. | Resultado/knowledge panel local posible. | Oficinas virtuales; reviews propias para estrellas; datos distintos de GBP/web. |
| `WebSite` | Identidad del sitio en home. | `name`, `alternateName`, `url`, `publisher`. | Puede ayudar con nombre del sitio; no “sube ranking”. | Usar `SearchAction` esperando sitelinks search box: esa función se retiró en 2024. |
| `WebPage` | Describir una página y relaciones. | `name`, `url`, `isPartOf`, `about`, `primaryImageOfPage`, `breadcrumb`. | Comprensión general; no rich result genérico garantizado. | Declarar datos no presentes o duplicar entidades sin `@id`. |
| `Service` | Servicio ofrecido y proveedor/área. | `name`, `description`, `provider`, `areaServed`, `offers` si es real. | Schema.org válido; no rich result genérico específico de Google. | Marcar cada keyword como servicio o inventar precios. |
| `Person` | Persona/autor real. | `name`, `url`, `image`, `jobTitle`, `worksFor`, `sameAs`. | Útil anidado; `ProfilePage` puede habilitar experiencia de perfil en casos válidos. | `Person` para una empresa; perfiles falsos. |
| `Article` | Artículo editorial/noticia/deporte. | `headline`, `image`, `datePublished`, `dateModified`, `author`. | Apariencia de artículo/fecha/imagen; soportado. | Cambiar `dateModified` sin cambio real; autor genérico inexistente. |
| `BlogPosting` | Subtipo de Article para blog. | Igual que Article; `publisher` cuando corresponda. | Hereda uso de Article; no bonus separado. | Marcar landings comerciales como posts. |
| `BreadcrumbList` | Breadcrumb visible y jerarquía. | `itemListElement`, `position`, `name`, `item`. | Breadcrumb en desktop; soportado. | Marcar ruta inexistente o distinta de navegación visible. |
| `FAQPage` | Página con FAQs visibles y una respuesta oficial por pregunta. | `mainEntity` con `Question`/`acceptedAnswer`. | **Desde 7-may-2026, Google dejó de mostrar FAQ rich results.** Puede seguir siendo schema válido; no prometer SERP. | Usarlo para foros, respuestas múltiples, contenido invisible o esperando estrellas/CTR. |
| `Product` | Producto específico vendible/reseñable. | `name`, `image`, `offers`, identificadores, `brand`, rating/review real. | Product snippet/merchant listing. | Usarlo en servicios genéricos; precio/stock desactualizado; reviews falsas. |
| `Review` | Reseña editorial o de usuario visible sobre entidad admitida. | `itemReviewed`, `author`, `reviewRating`, texto/fecha. | Review snippet solo para tipos y políticas soportados. | Reviews autocontroladas de Organization/LocalBusiness; markup sin reseña visible. |
| `AggregateRating` | Agregado real de múltiples ratings visibles. | `ratingValue`, `reviewCount` o `ratingCount`, escala. | Puede acompañar tipos admitidos. | Copiar rating de Google u otra plataforma sin mostrar/poseer datos; auto-serving. |
| `Event` | Evento público con fecha, ubicación y asistencia real. | `name`, `startDate`, `location`, `eventStatus`, `offers`, `organizer`. | Experiencia Event. | Horarios permanentes, promociones o cursos continuos sin evento concreto. |
| `Course` | Curso educativo real; Google Course list exige al menos tres cursos y disponibilidad por idioma/mercado. | `name`, `description`, `provider`; revisar propiedades vigentes. | Course list, disponible en inglés según documentación consultada. | Confundir servicio/clase recurrente con el rich result; asumir soporte universal. |

### Validación

1. Validar vocabulario/sintaxis en [Schema.org Validator](https://validator.schema.org/).
2. Validar elegibilidad Google en [Rich Results Test](https://search.google.com/test/rich-results).
3. Comprobar que datos coincidan con contenido renderizado.
4. Probar URLs publicadas con URL Inspection.
5. Monitorizar Enhancements y manual actions.
6. Revalidar tras cambios de plantilla y documentación.

> ⚠️ **OBSOLETO:** implementar FAQ schema esperando un rich result en Google; la función dejó de aparecer el 7 de mayo de 2026. [OFICIAL]([Search Console data anomalies](https://support.google.com/webmasters/answer/6211453))  
> ⚠️ **OBSOLETO:** `WebSite` + `SearchAction` para obtener el sitelinks search box; Google retiró esa función en noviembre de 2024.

---

## 14. SEO Local

### Modelo confirmado

Google declara tres grupos principales: **relevancia**, **distancia** y **prominencia**. No se puede pagar ni solicitar una mejor posición. [OFICIAL]([Improve local ranking](https://support.google.com/business/answer/7091))

| Señal/acción | Importancia estimada | Evidencia | Control | Nota |
|---|---|---|---|---|
| Elegibilidad y verificación de GBP | Crítica | `OFICIAL` | Alto | Perfil real, representación fiel y sin suspensiones. |
| Proximidad a quien busca | Muy alta | `OFICIAL` | Bajo | No falsear dirección; área de servicio no elimina distancia. |
| Categoría primaria correcta | Muy alta | `OFICIAL` + encuesta | Alto | Específica y representativa; no keyword stuffing. |
| Nombre real del negocio | Alta | `OFICIAL` | Alto | Debe coincidir con marca real; añadir keywords puede violar políticas. |
| Información completa/horarios | Alta | `OFICIAL` | Alto | Dirección/área, teléfono, horario normal y especial, servicios/atributos. |
| Reseñas auténticas, volumen/recencia/calidad | Alta | `OFICIAL` para cantidad/positividad; `EVIDENCIA MODERADA` para matices | Medio | Pedir sin incentivos ni gating; responder con utilidad. |
| Prominencia web y enlaces | Alta | `OFICIAL` en términos generales | Medio | Google cita enlaces y reconocimiento como componentes. |
| Página local relevante | Alta | `CONSENSO PROFESIONAL`/encuesta | Alto | Contenido propio, contacto, servicios y prueba de ubicación. |
| NAP coherente | Media–alta | `CONSENSO PROFESIONAL` | Alto | Priorizar fuentes importantes; no obsesionarse con puntuación perfecta. |
| Citations/directorios | Media | `EVIDENCIA MODERADA` | Medio | Calidad, relevancia y exactitud; no volumen basura. |
| Fotos/videos propios | Media para conversión; ranking exacto no público | `OFICIAL` para completar/atraer | Alto | Actualizados, representativos, sin depender de geotags como “hack”. |
| Posts GBP | Baja–media para conversión/frescura | `SIN EVIDENCIA SUFICIENTE` como gran factor | Alto | Útiles para usuarios; no asumir boost directo. |
| LocalBusiness schema | Media para comprensión | `OFICIAL` | Alto | No sustituye GBP ni crea Local Pack por sí solo. |
| Backlinks locales/editoriales | Media–alta | `CONSENSO PROFESIONAL` | Medio | Cámaras, asociaciones, prensa, socios reales; relevancia > paquete. |

La encuesta Whitespark 2026 reunió 47 especialistas y ponderó para Local Pack: señales GBP 32%, reviews 20%, on-page 15%, comportamiento 9%, enlaces 8%, citations/personalización 6% y social 4%. Es **opinión estructurada de expertos**, no pesos del algoritmo. [CONSENSO PROFESIONAL]([Whitespark 2026](https://whitespark.ca/local-search-ranking-factors/))

### Google Business Profile: estándar operativo

- Una ficha por negocio/ubicación elegible, con nombre usado en el mundo real.
- Dirección precisa; ocultarla si se atiende en domicilio del cliente. No P.O. box/oficina virtual.
- Categoría primaria que describa la actividad principal y pocas secundarias pertinentes.
- Horarios normales, especiales y “más horarios” cuando aplique.
- Teléfono y web oficiales por ubicación; evitar redirects/tracking que rompan consistencia.
- Servicios/productos/atributos veraces; descripción sin promociones agresivas ni URLs según políticas.
- Solicitar reseñas honestas a clientes reales; no ofrecer premios, no seleccionar solo satisfechos, no comprar.
- Responder reseñas; reportar solo las que violen políticas.
- Monitorizar ediciones sugeridas, duplicados, suspensiones y rendimiento.

### Páginas locales

**Crear** cuando exista una ubicación, equipo, oferta, logística, prueba o información realmente diferenciada. Incluir NAP, mapa/direcciones cuando útil, horario, servicios, evidencia local, preguntas reales y contacto.

**No crear** decenas de páginas de ciudades con el mismo contenido y sin presencia/cobertura comprobable. Pueden ser doorway pages o contenido programático sin valor.

### Medición local

- Conversiones de GBP: llamadas, rutas, reservas, clics, mensajes (según disponibilidad).
- Queries/páginas locales en GSC, conversiones en analítica y leads cualificados.
- Grid tracking geográfico solo como herramienta propietaria; la posición varía por ubicación y contexto.
- Comparar periodos equivalentes y anotar cambios de categoría, dirección, horario y algoritmos.

La [encuesta de consumidores BrightLocal 2026](https://www.brightlocal.com/research/local-consumer-review-survey/) ayuda a entender cómo las reseñas afectan selección y confianza, pero **no** demuestra que una conducta sea factor de ranking local. [`EVIDENCIA MODERADA`; encuesta de comportamiento]

---

## 15. Backlinks y autoridad

Google usa enlaces para descubrir páginas y como señales de relevancia. No publica un conteo óptimo ni equivale todos los enlaces. [OFICIAL]

### Evaluación de un enlace

Priorizar:

1. legitimidad editorial;
2. relación temática/local y contexto;
3. página real, indexable y con audiencia potencial;
4. anchor natural y diversidad;
5. riesgo de manipulación y sostenibilidad.

| Táctica | Evaluación 2026 |
|---|---|
| Digital PR con datos/historias propias | Recomendable: puede generar enlaces y menciones editoriales. |
| Recursos útiles/enlazables | Recomendable si resuelven necesidades reales. |
| Directorios sectoriales/locales legítimos | Contextual; útiles para descubrimiento/local, evitar granjas. |
| Guest post editorial genuino | Contextual; no escalar anchors exactos ni pagar para PageRank. |
| Menciones sin enlace | Pueden ayudar a notoriedad/entidad; efecto de ranking directo no confirmado. |
| Enlace pagado/publicitario | Debe usar `rel="sponsored"` o mecanismo equivalente; no comprar ranking. |
| UGC | Calificar con `rel="ugc"` cuando corresponda; moderar spam. |
| Intercambio ocasional real | Normal; intercambios excesivos para ranking son link spam. |
| PBN, automatización, paquetes | Alto riesgo; viola políticas si busca manipular. |
| Disavow | Solo ante acción manual o historial claro de enlaces artificiales; no limpieza rutinaria por score tóxico. |

La política de Google define como link spam la compra/venta para ranking, intercambios excesivos, programas automatizados, enlaces optimizados en artículos o widgets distribuidos, entre otros. [OFICIAL]([Spam policies](https://developers.google.com/search/docs/essentials/spam-policies))

### Métricas externas

- **Domain Authority (Moz)**
- **Domain Rating (Ahrefs)**
- **Authority Score (Semrush)**

son estimaciones propietarias, no métricas de Google ni objetivos en sí mismos. Google recuerda que terceros no acceden a su ranking interno. [OFICIAL]([Third-party SEO tools](https://developers.google.com/search/docs/fundamentals/third-party-seo))

Ahrefs observa correlación entre dominios de referencia, tráfico y rankings, pero correlación no prueba causalidad y sus métricas modelan su propio índice. [EVIDENCIA MODERADA]([Ahrefs search traffic study](https://ahrefs.com/blog/search-traffic-study/))

---

## 16. Entidades y Knowledge Graph

### Confirmado

- Google usa structured data, incluido `sameAs`, para comprender información y relaciones; `Organization` puede aportar identidad, logo, URL, contacto y perfiles. [OFICIAL]
- Knowledge panels combinan información de múltiples fuentes; estar en Wikipedia/Wikidata no garantiza panel ni ranking.
- La coherencia entre sitio, GBP, perfiles oficiales, registros y menciones reduce ambigüedad.

### Recomendación

- Definir una entidad principal con nombre oficial, alternativos reales, URL canónica, logo y contacto.
- Usar `@id` estable dentro del grafo JSON-LD para referenciar la misma entidad.
- `sameAs` solo a perfiles/páginas que identifican la misma entidad; no a cualquier mención.
- Mantener páginas About, autores/equipo y ubicaciones con datos verificables.
- Vincular marca–personas–servicios–lugares mediante contenido y relaciones reales.
- Conseguir menciones editoriales y directorios/registros relevantes, no fabricar Wikidata/Wikipedia para SEO.

### Inferencias que no deben elevarse a certeza

| Afirmación | Clasificación |
|---|---|
| La consistencia ayuda a desambiguar entidades. | `OFICIAL`/`CONSENSO PROFESIONAL` |
| `sameAs` garantiza Knowledge Panel. | `FALSO` |
| Wikidata es requisito para aparecer en respuestas de IA. | `SIN EVIDENCIA SUFICIENTE` |
| Existe un “entity score” público optimizable. | `SIN EVIDENCIA SUFICIENTE` |
| Menciones auténticas correlacionan con visibilidad en AIO. | `EVIDENCIA MODERADA`, no causalidad; Ahrefs halló ρ=0.664 en 75k marcas. |

Fuentes: [Organization structured data](https://developers.google.com/search/docs/appearance/structured-data/organization), [Ahrefs brand correlation study](https://ahrefs.com/blog/ai-overview-brand-correlation/).

---

## 17. SEO para buscadores y sistemas de IA

### Panorama 2026

| Sistema | Descubrimiento/controles confirmados | Medición disponible | Certeza |
|---|---|---|---|
| Google AI Overviews / AI Mode | Usa índice y sistemas centrales; página indexada y elegible con snippet; query fan-out/RAG; no requisito adicional. | GSC separa un **Generative AI performance report** en despliegue parcial; el reporte clásico también contiene datos según superficie/fecha. | `OFICIAL` |
| Gemini | Puede apoyarse en servicios de Google y web según producto; no existe factor SEO universal publicado distinto de Search. | Depende del producto; no asumir equivalencia con AIO. | `OFICIAL` limitado |
| ChatGPT Search | Permitir `OAI-SearchBot` para inclusión en resúmenes/snippets; separado de `GPTBot` de entrenamiento. Referidos usan `utm_source=chatgpt.com`. | Analítica de referidos y observación de citas; no Search Console público equivalente. | `OFICIAL` [OpenAI crawlers](https://developers.openai.com/api/docs/bots) |
| Bing/Copilot | Bing index, sitemaps, IndexNow y directivas; Webmaster Guidelines aplican a Search/Copilot. | Bing AI Performance (preview 2026): citas, páginas y grounding queries; no indica ranking/autoridad. | `OFICIAL` |
| Perplexity | Permitir `PerplexityBot` y sus IPs publicadas para aparecer; `Perplexity-User` es fetch bajo petición y generalmente ignora robots. | Referidos/citas y herramientas externas. | `OFICIAL` [Perplexity crawlers](https://docs.perplexity.ai/docs/resources/perplexity-crawlers) |

### GEO, AEO, LLMO y AI SEO

Son etiquetas útiles para distinguir objetivos de **citabilidad, menciones y respuestas**, pero gran parte de su ejecución es SEO clásico: acceso, indexación, contenido original, reputación, entidades y medición. Google declara explícitamente que, desde su perspectiva, AEO/GEO sigue siendo SEO y desaconseja hacks como chunking obligatorio, markup especial o menciones inauténticas. [OFICIAL]

Prácticas genuinamente adicionales o ampliadas:

- Gestionar bots de búsqueda IA por separado de bots de entrenamiento.
- Medir citas/menciones y referrals además de posiciones/clics.
- Diseñar contenido factual y verificable que pueda sostener respuestas compuestas.
- Evaluar volatilidad entre respuestas, modelos, ubicaciones y momentos.
- Preparar interfaces semánticas para agentes cuando exista caso de negocio.

---

## 18. Visibilidad y citabilidad en IA

### Factores con respaldo razonable

| Factor | Por qué puede ayudar | Evidencia | Límite |
|---|---|---|---|
| Accesibilidad/rastreo | Sin acceso, el sistema no recupera contenido propio. | `OFICIAL` por Google, OpenAI y Perplexity. | Algunos productos usan índices/proveedores o fetch bajo usuario. |
| Indexación y elegibilidad | Google exige estar indexado y elegible con snippet para AIO/AI Mode. | `OFICIAL` | No garantiza cita. |
| Relevancia específica | Retrieval necesita correspondencia con consulta/subconsulta. | `OFICIAL`/`EVIDENCIA FUERTE` | No existe densidad óptima. |
| Contenido no commodity/experiencia | Google 2026 lo prioriza como orientación principal. | `OFICIAL` | Calidad no se automatiza por completo. |
| Hechos, fuentes y estadísticas correctas | Pueden facilitar grounding y atribución. | `EXPERIMENTO`: GEO KDD 2024; guía Bing 2026. | Estudio GEO midió prominencia en contextos limitados, no ranking universal. |
| Estructura clara | Ayuda a usuarios y extracción; Bing aconseja headings/tablas/FAQ. | `OFICIAL` de Bing / `CONSENSO PROFESIONAL` | Google dice que no se requiere “chunking” especial. |
| Marca y menciones externas | Ahrefs halló correlación ρ=0.664 con menciones AIO en 75k marcas. | `EVIDENCIA MODERADA` | Correlación, no causalidad; no fabricar menciones. |
| Autoridad/reputación | Los sistemas buscan fuentes fiables y diversas. | `OFICIAL` general / `EVIDENCIA MODERADA` | Sin score público común. |
| Schema fiel | Desambigua y habilita features tradicionales. | `OFICIAL` | Google dice que no es obligatorio ni especial para IA. |
| Actualización | Reduce obsolescencia; sitemaps/IndexNow ayudan a descubrir cambios. | `OFICIAL` Bing/Google | Cambiar fecha sin contenido no ayuda. |

El paper GEO (KDD 2024) reportó hasta 40% de mejora en sus métricas de visibilidad al añadir citas, quotations y estadísticas en su benchmark, pero una revisión crítica 2026 destaca que evaluó una lista fija de cinco documentos y no el retrieval completo. Tratar como **experimento**, no promesa. [EXPERIMENTO]([GEO paper](https://dl.acm.org/doi/10.1145/3637528.3671900), [critical survey 2026](https://arxiv.org/html/2607.14035v1))

Un estudio Ahrefs de marzo de 2026 sobre 863 mil SERPs y 4 millones de URLs citadas encontró que solo 37.1% de las citas AIO coincidían con top 10 orgánico estándar; 36.7% no estaba en top 100. Esto demuestra diversidad de recuperación, no una fórmula para ser citado. [EVIDENCIA MODERADA]([Ahrefs 2026](https://ahrefs.com/blog/ai-overview-citations-top-10/))

### Impacto observado sobre clics y consumo

La presencia y efecto de AI Overviews dependen de mercado, fecha y consulta. Semrush observó AIO en aproximadamente 16% de más de 10 millones de keywords a finales de 2025; SISTRIX estimó cerca de 20% en su muestra alemana de febrero de 2026 y modeló una caída de CTR de la posición 1 de 27% a 11% cuando aparecía AIO. Ahrefs también observó menos clics en consultas con AIO, y un estudio académico de 2026 estimó alrededor de 15% de descenso de tráfico para páginas de Wikipedia expuestas. Son datasets/modelos específicos: prueban redistribución de clics en esos contextos, no un porcentaje universal ni una causa aplicable a todo sitio. [`EVIDENCIA MODERADA`; el diseño académico aporta evidencia causal dentro de su muestra]([Semrush](https://www.semrush.com/blog/semrush-ai-overviews-study/), [SISTRIX](https://www.sistrix.com/blog/ai-overviews-in-germany/), [Ahrefs](https://ahrefs.com/blog/ai-overviews-reduce-clicks/), [estudio académico](https://arxiv.org/abs/2602.18455))

### Medición responsable

- Registrar por plataforma: mención, URL citada, consulta/prompt, país, fecha y modelo/superficie.
- Separar **citado** de **mencionado**, **impresión**, **clic** y **conversión**.
- Repetir prompts: Ahrefs observó que 45.5% de citas cambian entre actualizaciones de AIO; la volatilidad invalida snapshots únicos. [EVIDENCIA MODERADA]
- Usar controles y series temporales; no atribuir crecimiento a una edición coincidente.
- Validar la cita: que respalde la afirmación y enlace a la URL correcta.

---

## 19. llms.txt y tecnologías emergentes

### `llms.txt`

| Pregunta | Respuesta 2026 |
|---|---|
| ¿Qué es? | Propuesta de Jeremy Howard/Answer.AI (septiembre 2024) para un archivo Markdown en `/llms.txt` que orienta a agentes hacia recursos útiles. |
| ¿Es estándar W3C/IETF? | No. Es una propuesta comunitaria/práctica emergente. |
| ¿Google Search lo usa? | No. Google declaró en julio de 2026 que lo ignora y que no ayuda ni perjudica rankings o visibilidad generativa. |
| ¿OpenAI/Perplexity/Bing prometen usarlo para ranking/citas? | No existe confirmación oficial pública suficiente en las fuentes revisadas. |
| ¿Puede tener utilidad? | Sí, experimentalmente para documentación o agentes que decidan leerlo de forma explícita. No sustituye HTML, sitemap, robots, APIs ni schema. |
| ¿Prioridad? | `EXPERIMENTAL`/BAJA; solo si es barato de mantener y hay consumidor/caso medible. |

Fuente de propuesta: [llmstxt.org](https://llmstxt.org/). Postura Google: [AI optimization guide](https://developers.google.com/search/docs/fundamentals/ai-optimization-guide).

> ⚠️ **OBSOLETO COMO RECOMENDACIÓN SEO:** vender `llms.txt` como requisito de Google o palanca de ranking/citas. Google confirma que no lo usa.

### Otras tecnologías emergentes

| Tecnología | Estado | Recomendación |
|---|---|---|
| IndexNow | Protocolo adoptado por Bing y otros para notificar altas/cambios/bajas. | `OFICIAL` para motores participantes; complementar sitemap, no sustituir calidad/indexación. |
| Search Console Generative AI report | Despliegue parcial en 2026; impresiones de AIO/AI Mode por página/país/fecha. | Adoptar cuando esté disponible; no interpretar impresiones como citas, clics o ranking. |
| Bing AI Performance | Preview pública 2026 con citas, páginas y grounding queries. | Usar para diagnóstico; Microsoft advierte que citation count no indica placement/authority. |
| UCP/agentes de comercio | Protocolo emergente mencionado por Google para experiencias agentic. | Vigilar si el proyecto tiene comercio; no requisito SEO universal. |
| Agent-friendly UX | Guía web.dev 2026: semántica, accesibilidad y acciones claras. | Aplicar por UX/automatización cuando relevante; beneficio SEO directo no demostrado. |

---

## 20. SEO para pequeñas empresas

| Acción | Impacto | Esfuerzo | Costo | Riesgo | Prioridad |
|---|---|---|---|---|---|
| Verificar y completar GBP real | Muy alto local | Bajo | Bajo | Bajo si cumple políticas | 1 |
| Asegurar DNS/HTTPS/uptime/indexabilidad | Muy alto | Medio | Bajo–medio | Alto si falla | 1 |
| Crear páginas de servicios y ubicaciones reales | Alto | Medio | Medio | Medio si se duplican | 1 |
| Configurar GSC y sitemap limpio | Alto diagnóstico | Bajo | Gratis | Bajo | 1 |
| Corregir titles/H1/contenido de páginas clave | Alto | Medio | Bajo | Bajo | 2 |
| Solicitar y responder reseñas auténticas | Alto local/conversión | Continuo | Bajo | Alto si incentiva/gatea | 2 |
| Mejorar velocidad móvil de plantillas principales | Alto UX, medio SEO | Medio | Variable | Bajo | 2 |
| NAP en directorios relevantes y perfiles oficiales | Medio | Bajo–medio | Bajo | Bajo | 3 |
| Obtener enlaces/menciones locales reales | Medio–alto | Medio–alto | Variable | Medio si manipulado | 3 |
| Publicar casos, datos y FAQs reales | Medio–alto | Medio | Medio | Bajo | 3 |
| Schema básico fiel | Medio | Bajo–medio | Bajo | Medio si abusivo | 3 |
| Blog diario genérico | Bajo/negativo | Alto | Alto | Alto por baja calidad | No priorizar |
| `llms.txt` sin consumidor medido | Desconocido | Bajo | Bajo | Bajo | Experimental |

**Orden recomendado:** accesibilidad técnica → presencia local/servicios → confianza y conversiones → contenido diferenciador → autoridad → experimentos.

---

## 21. Herramientas

| Herramienta | Qué mide/hace | Qué no mide | Tipo de métricas |
|---|---|---|---|
| Google Search Console | Rendimiento en Google, indexación, sitemaps, CWV, HTTPS, rich results, acciones y seguridad. | Tráfico total, conversiones completas, todos los ejemplos/queries; no crawler completo. | Oficial Google, con agregación/límites. |
| Google Analytics 4 | Sesiones, eventos, comportamiento y conversiones instrumentadas. | Posición/indexación; datos dependen de consentimiento, tags y atribución. | Primera parte del sitio; no métrica de ranking confirmada. |
| PageSpeed Insights | CrUX de campo + Lighthouse de laboratorio para URL/origen. | Experiencia universal si no hay muestra; una ejecución no prueba tendencia. | Oficial Chrome/Google. |
| Lighthouse | Auditoría sintética de performance, accesibilidad, prácticas y SEO básico; CI. | Indexación, intención, backlinks, calidad; no INP de usuarios reales. | Laboratorio oficial; score compuesto. |
| Chrome UX Report | Métricas reales agregadas Chrome, ventana 28 días, p75. | Todos los usuarios/navegadores; causa raíz detallada; URLs sin volumen. | Oficial campo. |
| Screaming Frog | Crawl técnico, extracción, render JS, enlaces, estados y plantillas. | Índice/ranking real de Google; calidad humana. | Datos observados por su crawler. |
| Ahrefs | Backlinks, keywords, estimaciones, DR/UR, AI visibility. | Datos internos de Google ni tráfico exacto. | Propietarias/modeladas. |
| Semrush | Keywords, visibilidad, auditoría, enlaces, estimaciones, IA. | Datos internos de Google ni causalidad. | Propietarias/modeladas. |
| SISTRIX | Visibility Index, SERPs, CTR/modelos y cambios. | Tráfico real universal ni ranking interno. | Propietarias/modeladas. |
| Moz | Link index, DA/PA, keywords y auditoría. | DA/PA no son métricas Google. | Propietarias/modeladas. |
| Bing Webmaster Tools | Rendimiento Bing, crawl/index, sitemaps, IndexNow, Site Scan, AI Performance preview. | Google; citation count no equivale a autoridad. | Oficial Microsoft. |
| Rich Results Test | Elegibilidad para rich results soportados por Google y render. | Toda validez Schema.org; aparición garantizada. | Oficial Google. |
| Schema.org Validator | Sintaxis/vocabulario Schema.org. | Elegibilidad/política de Google. | Estándar comunitario. |

**Regla:** usar herramientas externas para descubrir y priorizar hipótesis; confirmar con servidor, navegador y datos de primera parte. No perseguir DA/DR/Authority Score como KPI final.

---

## 22. Search Console

### Guía operativa

| Informe | Uso correcto | No sobrerreaccionar ante |
|---|---|---|
| Performance | Comparar clics, impresiones, CTR y posición por consulta/página/país/dispositivo/tipo; anotar releases. | Promedios globales mezclados; pequeñas variaciones; CTR sin considerar features e intención. |
| Generative AI performance | Cuando aparezca, analizar impresiones AIO/AI Mode por página/país/fecha. | Falta del informe (rollout parcial o poco volumen); impresiones no son clics ni posición. |
| Pages / Indexing | Ver si las URLs importantes están indexadas y detectar patrones. | Pretender 100% indexado; duplicados y URLs sin valor pueden excluirse correctamente. |
| Sitemaps | Validar lectura, errores y cobertura de conjuntos deseados. | “Success” como garantía de indexación o frescura inmediata. |
| Enhancements | Detectar errores de tipos rich result encontrados. | Warnings opcionales como incidentes críticos; rich result no garantizado. |
| Core Web Vitals | Ver grupos de URLs y datos de campo móvil/escritorio. | Cambios diarios o comparación directa con un Lighthouse aislado. |
| HTTPS | Identificar URLs no servidas/evaluadas por HTTPS. | Confundir HTTPS válido con garantía de ranking. |
| Manual Actions | Detectar sanciones manuales y alcance; corregir causa y reconsiderar. | Asumir que toda caída es acción manual. |
| Security Issues | Detectar hacking, malware, ingeniería social. | Ignorar una alerta: puede bloquear confianza y tráfico. |
| URL Inspection | Comparar versión indexada y prueba live; rendered HTML, canonical y recursos. | “URL can be indexed” como garantía; la prueba no evalúa todas las señales de calidad/seguridad. |
| Links | Muestra de enlaces externos/internos detectados. | Tratarlo como inventario exhaustivo o puntuación de calidad. |

### Procedimiento ante caída

1. Confirmar que la caída existe en clics y páginas/queries, no solo en promedio.
2. Consultar [Search Status Dashboard](https://status.search.google.com/summary) y anomalías de datos.
3. Comparar periodos equivalentes; después de core update, Google recomienda esperar una semana tras finalizar antes de analizar.
4. Separar demanda/estacionalidad, cambios SERP/IA, ranking, indexación y tracking.
5. Revisar releases, migraciones, servidor, robots/noindex/canonical y seguridad.
6. Inspeccionar muestras y logs; documentar hipótesis y evidencia.
7. Cambiar solo cuando exista causa razonable; no hacer rediseño reactivo por una fluctuación corta.

Fuentes: [Search Console overview](https://support.google.com/webmasters/answer/7451491), [Performance report](https://support.google.com/webmasters/answer/7576553), [URL Inspection](https://support.google.com/webmasters/answer/9012289), [Generative AI performance report](https://support.google.com/webmasters/answer/16984139), [debug traffic drops](https://developers.google.com/search/docs/monitor-debug/debugging-search-traffic-drops).

---

## 23. Mitos SEO que debemos dejar de repetir

| # | Afirmación | Veredicto | Explicación / evidencia |
|---:|---|---|---|
| 1 | Existe una densidad óptima de keywords. | **FALSO** | No hay porcentaje oficial; stuffing perjudica legibilidad y puede parecer spam. [Search Essentials](https://developers.google.com/search/docs/essentials) |
| 2 | Todo artículo necesita una longitud mínima. | **FALSO** | Google 2026 dice que no existe longitud ideal; depende de tarea/audiencia. [AI optimization guide](https://developers.google.com/search/docs/fundamentals/ai-optimization-guide) |
| 3 | Solo se permite un H1. | **FALSO** | No es requisito de Google; una jerarquía clara sigue siendo buena UX/accesibilidad. [SEO Starter Guide](https://developers.google.com/search/docs/fundamentals/seo-starter-guide) |
| 4 | El orden H2/H3 determina ranking. | **FALSO** | Google dice que el orden semántico no importa para Search; sí ayuda a lectores de pantalla. |
| 5 | El contenido IA se penaliza automáticamente. | **FALSO** | Se evalúan utilidad, calidad y propósito; la escala sin valor sí puede ser spam. [AI content guidance](https://developers.google.com/search/docs/fundamentals/using-gen-ai-content) |
| 6 | DA es un factor de Google. | **FALSO** | Es métrica de Moz; terceros no acceden a datos internos de ranking. |
| 7 | DR o Authority Score son factores de Google. | **FALSO** | Son métricas propietarias de Ahrefs/Semrush. |
| 8 | Más backlinks siempre implica mejor ranking. | **FALSO** | Calidad, relevancia, contexto y spam importan; correlación no es causalidad. |
| 9 | Schema mejora ranking directamente. | **SIN EVIDENCIA** | Ayuda a comprender y habilita rich results; no hay bonus general confirmado. |
| 10 | Core Web Vitals es un factor dominante. | **FALSO** | Se usa, pero relevancia puede prevalecer; no hay señal única de page experience. |
| 11 | Un sitemap garantiza indexación. | **FALSO** | Facilita descubrimiento y es señal canonical débil; no garantiza crawl/index. |
| 12 | Google usa Google Analytics para rankings. | **SIN EVIDENCIA** | No existe confirmación pública; GA es incompleto y configurable. No confundir medición con señal. |
| 13 | Bloquear en robots.txt elimina una URL del índice. | **FALSO** | Puede aparecer como URL sin snippet; usar noindex accesible, auth o eliminación. |
| 14 | `noindex` en robots.txt funciona. | **FALSO** | No soportado por Google. |
| 15 | Canonical obliga a Google. | **FALSO** | Es señal fuerte, no directiva; Google puede elegir otra. |
| 16 | Cada 404 perjudica el sitio. | **FALSO** | 404/410 son correctos para contenido sin reemplazo; corregir si rompe rutas útiles. |
| 17 | Redirigir todo a home conserva autoridad. | **FALSO** | Destinos irrelevantes pueden tratarse como soft 404 y dañan UX. |
| 18 | Hay que estar a máximo tres clics. | **PARCIAL** | Menor profundidad ayuda, pero tres no es regla oficial universal; evitar huérfanas sí importa. |
| 19 | Repetir la ciudad en todas partes mejora Local Pack. | **FALSO** | Relevancia local sí; stuffing y nombres GBP falsos violan políticas. |
| 20 | NAP debe ser tipográficamente idéntico en todo internet. | **PARCIAL** | Exactitud y consistencia importan; variaciones normales de formato no justifican obsesión. |
| 21 | Geotaggear fotos sube rankings locales. | **SIN EVIDENCIA** | No hay confirmación pública suficiente; priorizar fotos auténticas y GBP completo. |
| 22 | FAQ schema siempre produce desplegables. | **FALSO** | Práctica obsoleta: Google dejó de mostrar FAQ rich results el 7-may-2026. |
| 23 | `llms.txt` mejora Google AI Overviews. | **FALSO** | Google afirma que lo ignora y no ayuda ni perjudica. |
| 24 | Para IA hay que fragmentar todo en párrafos minúsculos. | **FALSO** | Google declara que no requiere chunking; estructurar para humanos. |
| 25 | GEO reemplazó al SEO. | **FALSO** | Hay medición y controles nuevos, pero Google considera AEO/GEO parte de SEO. |
| 26 | Estar top 10 garantiza cita en AI Overview. | **FALSO** | Ahrefs 2026 halló solo 37.1% de coincidencia con top 10 orgánico estándar. |
| 27 | Wikipedia/Wikidata garantiza Knowledge Panel. | **FALSO** | Puede aportar evidencia de entidad, pero no es requisito ni garantía. |
| 28 | La meta description es factor de ranking directo. | **SIN EVIDENCIA** | Influye en presentación/CTR cuando Google la usa; no factor directo confirmado. |
| 29 | Google siempre muestra el `<title>` exacto. | **FALSO** | Genera title links desde varias fuentes y puede reescribirlos. |
| 30 | Lighthouse 100 significa SEO perfecto. | **FALSO** | Es una prueba sintética limitada; no mide indexación, intención, autoridad ni calidad. |

---

## 24. Errores que pueden destruir el SEO de un sitio

| Error | Efecto | Detección | Prevención |
|---|---|---|---|
| `Disallow: /` en producción | Bloqueo de rastreo general. | Test robots/monitor de release. | Regla CI y smoke test postdeploy. |
| `noindex` global o por plantilla crítica | Retirada del índice al recrawl. | Crawl headers/DOM + GSC. | Assertions por ruta y environment. |
| `X-Robots-Tag: noindex` heredado | Desindexación incluso sin meta tag. | Headers. | Tests de servidor/CDN. |
| Canonical global a home/URL incorrecta | Consolidación o exclusión masiva. | Crawl de canonicals y diversidad. | Test por plantilla/URL. |
| Canonical a 3xx/4xx/noindex | Señales contradictorias. | Crawl graph. | Canonical a 200 indexable equivalente. |
| Migración sin mapa 1:1 | Pérdida de acceso, señales y tráfico. | Comparar inventarios y logs. | Mapa, staging, 301/308, monitor. |
| Redirect loops/chains | Fallo/latencia y rastreo incompleto. | Seguir hops. | Destino final directo. |
| Cambiar todas las URLs por estética | Riesgo innecesario. | Diff de rutas. | Mantener estabilidad. |
| SPA devuelve `200` para inexistentes | Soft 404 e index bloat. | URLs aleatorias + headers/render. | 404 real desde servidor/framework. |
| Contenido principal solo tras acción | Crawlers no lo ven o retrasan. | Render sin scroll/click. | SSR/SSG o carga observable. |
| JS/CSS bloqueado o bundles fallidos | Render vacío/parcial. | URL Inspection/logs/consola. | Permitir recursos y monitor SLO. |
| WAF bloquea bots verificados | Caída de crawl/index. | 403/429 por UA/IP. | Verificación oficial y reglas seguras. |
| 5xx/timeout sostenido | Menor rastreo y posibles caídas. | Uptime/logs/Crawl Stats. | Capacidad, caché, alertas, rollback. |
| DNS o TLS roto/certificado incorrecto | Inaccesibilidad/seguridad. | Monitor externo y expiración. | Renovación automática y alertas. |
| HTTP/HTTPS, www/no-www duplicados | Duplicación y señales divididas. | Crawl variantes. | Redirect/canonical/HSTS coherentes. |
| Sitemap con staging o noindex | Descubrimiento de URLs erróneas. | Validación sitemap. | Generar desde fuente canónica. |
| Facetas/calendarios infinitos | Crawl trap e index bloat. | Logs y patrones. | Límites, enlaces controlados, reglas. |
| Páginas locales clonadas | Doorway/thin content y mala experiencia. | Similitud por plantilla. | Solo ubicaciones/ofertas reales y únicas. |
| Contenido programático sin QA | Spam, errores y baja confianza. | Muestreo/datos/quejas. | Gates editoriales y publicación gradual. |
| Sitio hackeado/UGC spam | Alertas de seguridad, páginas basura, reputación. | GSC Security, logs, scans. | Parches, auth, moderación y backups. |
| Schema falso/ratings propios | Pérdida de rich results/acción manual. | Comparar visible vs JSON-LD. | Generar desde mismos datos visibles. |
| Internal links a no canonical/redirect | Señales y crawl desperdiciados. | Crawl inlinks. | Enlazar directo a canonical 200. |
| Eliminación de contenido con tráfico sin evaluación | Pérdida de demanda/enlaces. | GSC/analytics/backlinks. | Consolidar o redirigir cuando exista equivalente. |
| Robots bloquea página con `noindex` | Motor no ve la exclusión. | Test combinado. | Permitir crawl hasta procesar noindex. |

---

## 25. Matriz de prioridades

### Fórmula de decisión

```text
Prioridad = severidad × alcance × confianza de evidencia × valor de negocio ÷ esfuerzo
```

No usar como matemática falsa: sirve para ordenar y documentar supuestos.

### CRÍTICO

- DNS, HTTPS, uptime o servidor impiden acceso.
- Robots/noindex/headers bloquean URLs esenciales.
- Render devuelve vacío o error a crawlers/usuarios.
- Canonicalización o migración elimina/consolida masivamente.
- Seguridad comprometida, malware o acción manual grave.

### ALTO

- Duplicación/facetas a escala; sitemaps contradictorios.
- Arquitectura huérfana o navegación no rastreable.
- Contenido esencial insuficiente/incorrecto o páginas doorway.
- GBP suspendido, inelegible o con datos falsos.
- Redirecciones/estados incorrectos con tráfico/backlinks.

### MEDIO

- Titles/descriptions/anchors débiles en plantillas relevantes.
- CWV deficientes con datos de campo y oportunidad real.
- Schema soportado ausente/erróneo sin riesgo de indexación.
- Accesibilidad, imágenes y contenido secundario mejorables.
- Citations y perfiles importantes inconsistentes.

### BAJO

- Preferencias de formato URL sin duplicación.
- Warnings opcionales de schema.
- Microoptimizaciones de score sin impacto de campo.
- Perfección semántica que no cambia accesibilidad/UX.

### EXPERIMENTAL

- `llms.txt` para consumidores identificados.
- Ajustes de citabilidad evaluados con experimentos controlados.
- Protocolos agentic emergentes sin caso de uso establecido.

### Plantilla de hallazgo

```markdown
ID: SEO-AREA-NNN
Estado: PASS | WARNING | FAIL | N/A
Severidad: CRÍTICA | ALTA | MEDIA | BAJA | EXPERIMENTAL
Evidencia: OFICIAL | EVIDENCIA FUERTE | EVIDENCIA MODERADA | EXPERIMENTO | CONSENSO PROFESIONAL | HIPÓTESIS | SIN EVIDENCIA SUFICIENTE
Alcance: URL | plantilla | directorio | sitio | entidad externa
Observación:
Evidencia observada:
Impacto probable:
Corrección propuesta:
Cómo validar:
Excepciones/contexto:
Propietario:
```

---

## 26. Checklist técnico maestro

### Cómo marcar

- `PASS`: cumple el criterio y existe evidencia comprobada.
- `WARNING`: riesgo contextual, muestra insuficiente o mejora no bloqueante.
- `FAIL`: incumplimiento confirmado y accionable.
- `N/A`: no aplica; documentar por qué.

Sustituir la casilla por el estado, por ejemplo: `- [x] PASS — SEO-CRAWL-001 — ...`.

### Servidor, DNS, HTTPS y seguridad

- [ ] El dominio y subdominios canónicos resuelven por DNS sin errores intermitentes.
- [ ] El host canónico responde y las variantes redirigen directamente a él.
- [ ] HTTPS usa certificado válido, cadena completa, hostname correcto y renovación monitorizada.
- [ ] HTTP redirige una sola vez a la URL HTTPS equivalente.
- [ ] Las URLs importantes responden `200` con contenido válido, no shell/error.
- [ ] Los fallos reales responden `5xx`, no `200` con mensaje de error.
- [ ] La latencia y tasa 5xx se monitorizan desde fuera de la infraestructura.
- [ ] CDN/WAF permite bots verificados y no devuelve 403/429 sistemáticos.
- [ ] No hay mixed content crítico ni redirects HTTPS→HTTP.
- [ ] Search Console no muestra Security Issues ni Manual Actions sin atender.
- [ ] CMS/framework/dependencias y servidor tienen proceso de parches.
- [ ] Formularios, UGC y cuentas tienen controles contra abuso/spam.

### Rastreo y robots

- [ ] `/robots.txt` responde `200`, sintaxis válida y política intencional.
- [ ] `robots.txt` no contiene bloqueo global accidental en producción.
- [ ] CSS, JS e imágenes necesarios para renderizar no están bloqueados.
- [ ] No se usa robots.txt para proteger datos privados.
- [ ] No se intenta declarar `noindex` dentro de robots.txt.
- [ ] Meta robots coincide con la intención por plantilla.
- [ ] `X-Robots-Tag` fue auditado en HTML, PDF, imágenes y otros recursos relevantes.
- [ ] `noindex` importante es visible al crawler y no está oculto tras un Disallow.
- [ ] Navegación y enlaces principales usan `<a href>` resoluble.
- [ ] Logs no muestran crawl traps, 5xx, timeouts o bloqueos dominantes.
- [ ] Parámetros de tracking no se propagan por enlaces internos.
- [ ] Filtros, calendarios, búsquedas e infinite scroll tienen límites rastreables.

### Sitemaps, estados y redirects

- [ ] El sitemap contiene solo URLs canónicas, `200`, indexables y deseadas.
- [ ] El sitemap no incluye staging, parámetros, redirects, 4xx o `noindex`.
- [ ] Los `lastmod` reflejan cambios sustantivos reales.
- [ ] El sitemap cumple límites de tamaño/cantidad y está declarado/subido.
- [ ] 301/308 se usa para movimientos permanentes y 302/307 para temporales.
- [ ] No hay redirect loops.
- [ ] Las cadenas importantes apuntan directo al destino final.
- [ ] Redirects llevan a equivalentes relevantes, no masivamente a home.
- [ ] 404/410 se usa para contenido retirado sin sustituto.
- [ ] No existen soft 404 recurrentes en plantillas o estados vacíos.

### Indexación y canonicals

- [ ] Cada plantilla indexable tiene canonical absoluto y coherente.
- [ ] La canonical autorreferente apunta a una URL `200` e indexable.
- [ ] No hay canonicals a redirects, 4xx, `noindex` o contenido no equivalente.
- [ ] Enlaces internos, sitemap, hreflang y canonical señalan la misma preferencia.
- [ ] Variantes HTTP/HTTPS, host, mayúsculas y slash están consolidadas.
- [ ] Las URLs importantes aparecen indexadas o tienen diagnóstico documentado.
- [ ] “Crawled” y “Discovered – currently not indexed” se analizan por patrón/muestra.
- [ ] Duplicados elegidos por Google son intencionales o tienen plan de alineación.
- [ ] Búsqueda interna y filtros no generan index bloat sin valor.
- [ ] No se exige que toda URL conocida esté indexada.

### URLs y arquitectura

- [ ] Las URLs son estables, legibles y usan minúsculas/guiones según política.
- [ ] No hay IDs de sesión ni parámetros inútiles en URLs indexables.
- [ ] Cada página importante recibe al menos un enlace interno rastreable.
- [ ] No existen páginas huérfanas importantes en sitemap/analytics/logs.
- [ ] La navegación móvil mantiene enlaces y contenido esenciales.
- [ ] Categorías y hubs aportan orientación, no solo listas vacías.
- [ ] Breadcrumbs visibles representan la jerarquía real.
- [ ] Paginación tiene URLs y enlaces secuenciales accesibles.
- [ ] Páginas solapadas/canibalizadas tienen intención diferenciada o consolidación.
- [ ] Páginas locales corresponden a ubicaciones/cobertura reales y contenido propio.

### Contenido y On-Page

- [ ] Cada URL indexable tiene propósito, audiencia e intención principales documentados.
- [ ] `<title>` es específico, fiel, distintivo y no stuffed.
- [ ] Existe un heading principal visible que describe la página.
- [ ] Subheadings organizan contenido para usuarios, sin cuotas arbitrarias.
- [ ] Meta description resume valor y no duplica masivamente plantillas.
- [ ] El contenido principal está disponible en texto cuando sea importante.
- [ ] Hechos sensibles/temporales incluyen fuentes y fecha de revisión.
- [ ] Autoría, organización, contacto y método son claros cuando importan.
- [ ] El contenido aporta experiencia, datos, ejemplos o análisis propios.
- [ ] No hay páginas creadas solo por variantes de keywords.
- [ ] No existe keyword stuffing en body, titles, anchors o alt.
- [ ] Contenido IA/programático tiene revisión, trazabilidad y retirada de fallos.
- [ ] Contenido duplicado externo/interno tiene justificación y tratamiento.
- [ ] Enlaces externos relevantes apuntan a fuentes fiables y vigentes.

### Imágenes, multimedia y enlaces

- [ ] Imágenes informativas tienen alt útil; decorativas usan alt vacío.
- [ ] Dimensiones o `aspect-ratio` reservan espacio y evitan CLS.
- [ ] Imágenes responsive usan tamaños/formatos apropiados.
- [ ] El recurso LCP no se lazy-loadea de forma perjudicial.
- [ ] Video/audio esencial tiene texto, captions o transcripción cuando corresponde.
- [ ] Anchors internos describen destino y evitan patrones artificiales.
- [ ] Enlaces pagados usan `sponsored`; UGC usa `ugc`/moderación según contexto.
- [ ] No hay enlaces internos rotos ni a cadenas evitables.

### JavaScript y renderizado

- [ ] Cada ruta indexable responde directamente al deep link.
- [ ] HTML inicial o render verificable contiene contenido principal.
- [ ] Metadata y canonical son correctos por ruta antes/después de hydration.
- [ ] Rutas inexistentes devuelven 404 real, no SPA `200` genérico.
- [ ] Contenido crítico no exige scroll, click o consentimiento no esencial para cargar.
- [ ] Errores JS/API no dejan páginas vacías con `200`.
- [ ] Fuente, DOM renderizado y URL Inspection son sustancialmente equivalentes.
- [ ] Dynamic rendering, si existe, es temporal, equivalente y monitorizado.

### Rendimiento, móvil y accesibilidad

- [ ] CrUX/GSC muestra LCP p75 ≤2.5 s o existe plan por plantilla.
- [ ] CrUX/GSC muestra INP p75 ≤200 ms o existe plan por interacción.
- [ ] CrUX/GSC muestra CLS p75 ≤0.10 o existe plan por causa.
- [ ] TTFB y FCP se usan como diagnóstico, no se confunden con CWV.
- [ ] Se distinguen datos de campo y laboratorio en cada informe.
- [ ] Existe presupuesto de performance y prueba de regresión para plantillas clave.
- [ ] Viewport, tipografía, zoom, orientación y touch targets funcionan en móvil.
- [ ] Contenido y metadata tienen paridad móvil/escritorio.
- [ ] El sitio es operable con teclado y muestra foco.
- [ ] Controles tienen nombre/label accesible y errores comprensibles.
- [ ] Landmarks/headings describen estructura y ARIA no sustituye HTML nativo sin razón.
- [ ] Contraste y texto alternativo fueron revisados también de forma humana.

### Datos estructurados

- [ ] JSON-LD o formato elegido es sintácticamente válido.
- [ ] Tipos y propiedades describen contenido visible real.
- [ ] Rich Results Test no presenta errores críticos para tipos soportados.
- [ ] Organization/LocalBusiness usa entidad, URL, logo y datos coherentes.
- [ ] BreadcrumbList coincide con breadcrumbs visibles.
- [ ] Product/Event/Course/Article cumple políticas y propiedades vigentes si aplica.
- [ ] Review/AggregateRating no es autocontrolado ni copiado indebidamente.
- [ ] FAQPage no se implementa esperando rich result de Google en 2026.
- [ ] Schema válido pero no soportado no se vende como rich result.

### SEO local, autoridad, entidades e IA

- [ ] GBP es elegible, verificado, sin duplicados y representa el nombre real.
- [ ] Categoría primaria y secundarias reflejan actividades reales.
- [ ] Dirección/área, teléfono, web, horarios normales y especiales están actualizados.
- [ ] Reseñas se solicitan sin incentivos/gating y se responden con política clara.
- [ ] NAP es exacto en sitio, GBP y fuentes locales/sectoriales principales.
- [ ] Cada ubicación real tiene landing diferenciada cuando aporta valor.
- [ ] Backlinks/menciones se adquieren editorialmente; no hay PBN/paquetes/intercambios excesivos.
- [ ] DA, DR y Authority Score se tratan como métricas externas, no factores Google.
- [ ] Organization/Person/Place usa `sameAs` solo para identidades equivalentes.
- [ ] Marca, perfiles oficiales, autores y datos legales/operativos no se contradicen.
- [ ] `OAI-SearchBot`, Bingbot y PerplexityBot tienen política deliberada y documentada.
- [ ] `GPTBot` se decide separadamente de la inclusión en ChatGPT Search.
- [ ] La medición IA separa impresión, mención, cita, clic y conversión.
- [ ] `llms.txt`, si existe, está marcado como experimento y tiene consumidor/medición.
- [ ] No se crean menciones, páginas o schema artificiales solo para influir respuestas IA.

### Search Console y observabilidad

- [ ] Propiedad de dominio GSC está verificada con propietarios correctos.
- [ ] Performance se segmenta por página, consulta, país, dispositivo y tipo.
- [ ] Releases/migraciones se anotan y comparan con periodos equivalentes.
- [ ] Pages se evalúa contra URLs deseadas, no contra 100% de cobertura.
- [ ] URL Inspection se usa con muestras de cada patrón y páginas sanas de control.
- [ ] Sitemaps, Enhancements, CWV, HTTPS, Manual Actions y Security se revisan periódicamente.
- [ ] Anomalías de datos y Search Status se consultan antes de atribuir caídas.
- [ ] Datos GSC se exportan para conservar series más largas cuando sea necesario.

---

## 27. Reglas automatizables

### Convención

- Una regla produce `PASS`, `WARNING`, `FAIL` o `N/A`; nunca “corrige” automáticamente producción.
- La condición se evalúa sobre la población definida (sitio, plantilla o muestra). Un único `FAIL` no implica siempre impacto masivo.
- `YES` significa prueba determinista; `PARTIAL`, detección automática con interpretación humana; `NO`, juicio principalmente humano.
- Umbrales de volumen, tiempo y cobertura deben configurarse por proyecto. No convertir un número orientativo en ley universal.

| ID | Regla | Condición PASS / FAIL | Severidad | Evidencia | Automatizable |
|---|---|---|---|---|---|
| SEO-ACCESS-001 | DNS resuelve los hosts canónicos | PASS: A/AAAA/CNAME válidos; FAIL: NXDOMAIN/timeout | CRÍTICA | OFICIAL | YES |
| SEO-ACCESS-002 | HTTPS válido | PASS: cadena, hostname y vigencia correctos; FAIL: error TLS | CRÍTICA | OFICIAL | YES |
| SEO-ACCESS-003 | Host preferido único | PASS: variantes redirigen al host canónico; FAIL: duplicados 200 | ALTA | OFICIAL | YES |
| SEO-ACCESS-004 | Disponibilidad de plantillas críticas | PASS: SLO cumplido; FAIL: 5xx/timeout sostenido | CRÍTICA | OFICIAL | YES |
| SEO-ACCESS-005 | Bots verificados no bloqueados por WAF/CDN | PASS: respuestas equivalentes legítimas; FAIL: 403/429 selectivo accidental | CRÍTICA | OFICIAL | PARTIAL |
| SEO-SECURITY-001 | Sin interstitial de malware/phishing | PASS: sin alerta; FAIL: alerta confirmada | CRÍTICA | OFICIAL | PARTIAL |
| SEO-SECURITY-002 | No hay secretos ni paneles en URLs indexables | PASS: inaccesibles/no públicos; FAIL: exposición | CRÍTICA | CONSENSO PROFESIONAL | PARTIAL |
| SEO-SECURITY-003 | Dependencias y CMS reciben parches | PASS: política/SLA cumplido; FAIL: vulnerabilidad explotable vencida | ALTA | CONSENSO PROFESIONAL | PARTIAL |
| SEO-CRAWL-001 | `robots.txt` accesible | PASS: `/robots.txt` devuelve archivo procesable; FAIL: bloqueo o 5xx persistente | ALTA | OFICIAL | YES |
| SEO-CRAWL-002 | Producción no contiene `Disallow: /` global accidental | PASS: ausencia o decisión documentada; FAIL: bloqueo involuntario | CRÍTICA | OFICIAL | YES |
| SEO-CRAWL-003 | Directivas robots usan sintaxis soportada | PASS: grupos y patrones válidos; FAIL: dependencia de reglas no soportadas | ALTA | OFICIAL | YES |
| SEO-CRAWL-004 | Recursos críticos de render son rastreables | PASS: JS/CSS/API públicos necesarios accesibles; FAIL: bloqueados | ALTA | OFICIAL | PARTIAL |
| SEO-CRAWL-005 | Enlaces internos son `<a href>` resolubles | PASS: destino en `href`; FAIL: navegación esencial solo por evento JS | ALTA | OFICIAL | YES |
| SEO-CRAWL-006 | No hay crawl traps evidentes | PASS: espacio de URLs acotado; FAIL: combinaciones/calendarios infinitos | ALTA | OFICIAL | PARTIAL |
| SEO-CRAWL-007 | Parámetros tienen política documentada | PASS: función, enlace, canonical e indexación definidos; FAIL: proliferación sin control | ALTA | CONSENSO PROFESIONAL | PARTIAL |
| SEO-CRAWL-008 | Paginación enlaza páginas necesarias | PASS: cada página alcanzable; FAIL: contenido solo tras acciones no rastreables | ALTA | OFICIAL | PARTIAL |
| SEO-CRAWL-009 | Enlaces rotos internos bajo control | PASS: ninguno en navegación/plantillas; FAIL: 4xx en rutas útiles | MEDIA | CONSENSO PROFESIONAL | YES |
| SEO-SITEMAP-001 | Sitemap responde 200 y XML válido | PASS: válido; FAIL: inaccesible/malformado | ALTA | OFICIAL | YES |
| SEO-SITEMAP-002 | Sitemap solo lista URLs canónicas elegibles | PASS: 200, indexables y canónicas; FAIL: 3xx/4xx/noindex/duplicadas | ALTA | OFICIAL | YES |
| SEO-SITEMAP-003 | Límites de sitemap se respetan | PASS: ≤50.000 URLs y ≤50 MB sin comprimir por archivo; FAIL: excede | MEDIA | OFICIAL | YES |
| SEO-SITEMAP-004 | `lastmod` es fiable | PASS: cambia con contenido significativo; WARNING: fechas artificiales | MEDIA | OFICIAL | PARTIAL |
| SEO-HTTP-001 | URLs existentes devuelven 200 | PASS: contenido válido y 2xx; FAIL: estado incoherente | ALTA | OFICIAL | YES |
| SEO-HTTP-002 | URLs inexistentes devuelven 404/410 | PASS: estado real; FAIL: plantilla vacía con 200 | ALTA | OFICIAL | YES |
| SEO-HTTP-003 | Sin soft 404 en plantillas indexables | PASS: valor real; FAIL: vacío/error con 200 | ALTA | OFICIAL | PARTIAL |
| SEO-HTTP-004 | Errores 5xx no son sostenidos | PASS: bajo SLO; FAIL: patrón persistente/material | CRÍTICA | OFICIAL | YES |
| SEO-HTTP-005 | Respuestas no dependen incorrectamente del user-agent | PASS: contenido equivalente; FAIL: cloaking/bloqueo accidental | CRÍTICA | OFICIAL | PARTIAL |
| SEO-REDIRECT-001 | Redirect permanente usa 301/308 cuando corresponde | PASS: cambio permanente; FAIL: temporal indefinido/incoherente | ALTA | OFICIAL | YES |
| SEO-REDIRECT-002 | Sin loops | PASS: destino final alcanzable; FAIL: ciclo | CRÍTICA | OFICIAL | YES |
| SEO-REDIRECT-003 | Sin cadenas evitables | PASS: enlace y redirect apuntan al destino final; WARNING: >1 salto | MEDIA | OFICIAL | YES |
| SEO-REDIRECT-004 | Destino es equivalente | PASS: conserva intención/contenido; FAIL: home irrelevante/soft 404 | ALTA | OFICIAL | PARTIAL |
| SEO-REDIRECT-005 | Migración conserva mapa URL a URL | PASS: cobertura documentada; FAIL: rutas con valor sin destino adecuado | CRÍTICA | OFICIAL | PARTIAL |
| SEO-INDEX-001 | Páginas objetivo no tienen `noindex` | PASS: directiva ausente; FAIL: meta/header `noindex` | CRÍTICA | OFICIAL | YES |
| SEO-INDEX-002 | Exclusiones deliberadas usan método correcto | PASS: auth/noindex/404 según caso; FAIL: solo robots para desindexar | ALTA | OFICIAL | PARTIAL |
| SEO-INDEX-003 | Robots no impide ver un `noindex` necesario | PASS: URL rastreable hasta procesar directiva; FAIL: combinación contradictoria | ALTA | OFICIAL | YES |
| SEO-INDEX-004 | Páginas indexables tienen contenido principal | PASS: contenido útil visible; FAIL: vacío/thin sistémico | ALTA | OFICIAL | PARTIAL |
| SEO-INDEX-005 | Huérfanas objetivo inexistentes | PASS: cada URL objetivo recibe enlace interno; FAIL: solo sitemap | ALTA | CONSENSO PROFESIONAL | YES |
| SEO-INDEX-006 | Estados GSC se interpretan por intención | PASS: muestra + patrón + logs; FAIL: acción indiscriminada por etiqueta | MEDIA | OFICIAL | NO |
| SEO-CANONICAL-001 | Canonical absoluto y resoluble | PASS: URL absoluta válida; FAIL: vacío/malformado | ALTA | OFICIAL | YES |
| SEO-CANONICAL-002 | Canonical apunta a 200 indexable | PASS: destino 200 sin noindex; FAIL: 3xx/4xx/5xx/noindex | ALTA | OFICIAL | YES |
| SEO-CANONICAL-003 | Una canonical por documento | PASS: señal única; FAIL: múltiples conflictivas | ALTA | OFICIAL | YES |
| SEO-CANONICAL-004 | Señales de canonicalización son coherentes | PASS: redirect, HTML, sitemap e internos convergen; FAIL: conflicto | ALTA | OFICIAL | YES |
| SEO-CANONICAL-005 | Alternativas son realmente equivalentes | PASS: duplicado/subconjunto legítimo; FAIL: contenido distinto consolidado | ALTA | OFICIAL | PARTIAL |
| SEO-CANONICAL-006 | Canonical declarada vs elegida se muestrea | PASS: coincidencia o excepción explicada; WARNING: divergencia sistémica | ALTA | OFICIAL | PARTIAL |
| SEO-URL-001 | URLs estables y descriptivas | PASS: identificador legible/estable; WARNING: opacas o volátiles sin necesidad | MEDIA | OFICIAL | PARTIAL |
| SEO-URL-002 | Una política de mayúsculas y slash | PASS: variantes redirigen/consolidan; FAIL: duplicados 200 | ALTA | OFICIAL | YES |
| SEO-URL-003 | Fragmentos no representan páginas independientes | PASS: estado indexable tiene URL de servidor; FAIL: routing solo `#` | ALTA | OFICIAL | YES |
| SEO-URL-004 | Parámetros de tracking no crean internos duplicados | PASS: enlaces limpios/canonical coherente; FAIL: proliferación | MEDIA | OFICIAL | YES |
| SEO-ARCH-001 | Navegación principal es rastreable | PASS: enlaces HTML a categorías/servicios; FAIL: destinos inaccesibles | ALTA | OFICIAL | PARTIAL |
| SEO-ARCH-002 | Profundidad de páginas prioritarias es razonable | PASS: alcanzables según arquitectura; WARNING: profundidad anómala | MEDIA | CONSENSO PROFESIONAL | YES |
| SEO-ARCH-003 | Breadcrumbs reflejan jerarquía | PASS: visibles, enlazados y coherentes; WARNING: discrepancia | MEDIA | OFICIAL | PARTIAL |
| SEO-ARCH-004 | No hay páginas de categoría vacías indexables | PASS: valor/navegación real; FAIL: combinaciones vacías a escala | ALTA | CONSENSO PROFESIONAL | PARTIAL |
| SEO-TITLE-001 | Cada página indexable tiene `<title>` | PASS: no vacío; FAIL: ausente/vacío | ALTA | OFICIAL | YES |
| SEO-TITLE-002 | Titles no son duplicados sistémicos | PASS: describen propósito/entidad; WARNING: duplicación en páginas distintas | MEDIA | OFICIAL | PARTIAL |
| SEO-TITLE-003 | Title evita stuffing/boilerplate dominante | PASS: conciso y descriptivo; WARNING: repetición artificial | MEDIA | OFICIAL | PARTIAL |
| SEO-META-001 | Meta description válida donde aporta | PASS: descripción útil o decisión de omitir; WARNING: duplicada/engañosa | BAJA | OFICIAL | PARTIAL |
| SEO-HEADING-001 | Contenido tiene jerarquía comprensible | PASS: headings describen secciones; FAIL: estructura engañosa/inaccesible | MEDIA | OFICIAL | PARTIAL |
| SEO-CONTENT-001 | Contenido principal coincide con intención declarada | PASS: satisface tarea; FAIL: doorway/keyword-only | ALTA | OFICIAL | NO |
| SEO-CONTENT-002 | Datos factuales tienen fuente/fecha cuando importa | PASS: trazables y actuales; WARNING: afirmaciones sensibles sin respaldo | ALTA | OFICIAL | PARTIAL |
| SEO-CONTENT-003 | Contenido generado a escala aporta valor | PASS: utilidad y QA demostrables; FAIL: páginas masivas sin valor | ALTA | OFICIAL | NO |
| SEO-CONTENT-004 | No hay keyword stuffing | PASS: lenguaje natural; FAIL: repetición manipuladora | ALTA | OFICIAL | PARTIAL |
| SEO-CONTENT-005 | Autores y responsabilidades no son ficticios | PASS: identidad/transparencia adecuadas; FAIL: representación engañosa | ALTA | OFICIAL | PARTIAL |
| SEO-CONTENT-006 | Fechas no se actualizan sin cambio sustancial | PASS: fecha refleja revisión real; WARNING: freshness artificial | MEDIA | OFICIAL | PARTIAL |
| SEO-IMAGE-001 | Imágenes informativas tienen alt contextual | PASS: alt útil; FAIL: ausente/inadecuado a escala | MEDIA | OFICIAL | PARTIAL |
| SEO-IMAGE-002 | Imágenes decorativas usan alt vacío | PASS: `alt=""`; WARNING: ruido redundante | BAJA | OFICIAL | YES |
| SEO-IMAGE-003 | Dimensiones/aspect ratio reservan espacio | PASS: espacio conocido; WARNING: fuente probable de CLS | MEDIA | EVIDENCIA FUERTE | YES |
| SEO-IMAGE-004 | Recurso LCP no se retrasa por lazy-load | PASS: carga prioritaria razonable; FAIL: `loading=lazy` perjudicial | ALTA | EVIDENCIA FUERTE | PARTIAL |
| SEO-JS-001 | Deep links responden directamente | PASS: cada ruta carga por URL; FAIL: requiere navegación previa | CRÍTICA | OFICIAL | YES |
| SEO-JS-002 | HTML renderizado contiene contenido esencial | PASS: contenido/enlaces/metadata presentes; FAIL: render vacío | CRÍTICA | OFICIAL | PARTIAL |
| SEO-JS-003 | SPA devuelve 404 real | PASS: estado 404 para ruta inexistente; FAIL: 200 genérico | ALTA | OFICIAL | YES |
| SEO-JS-004 | Metadata es única por ruta | PASS: title/canonical/robots correctos; FAIL: valores globales/tardíos | ALTA | OFICIAL | YES |
| SEO-JS-005 | Contenido no requiere interacción para existir | PASS: carga sin scroll/click; FAIL: contenido esencial oculto al crawler | ALTA | OFICIAL | PARTIAL |
| SEO-JS-006 | Hydration no elimina/cambia contenido crítico | PASS: paridad; FAIL: mismatch material | ALTA | CONSENSO PROFESIONAL | PARTIAL |
| SEO-JS-007 | Dynamic rendering conserva equivalencia | PASS: contenido equivalente y controlado; FAIL: divergencia/cloaking | CRÍTICA | OFICIAL | PARTIAL |
| SEO-SCHEMA-001 | Marcado es sintácticamente válido | PASS: validator sin errores; FAIL: JSON-LD/microdata inválido | MEDIA | OFICIAL | YES |
| SEO-SCHEMA-002 | Marcado coincide con contenido visible | PASS: mismas entidades/datos; FAIL: datos ocultos/falsos | ALTA | OFICIAL | PARTIAL |
| SEO-SCHEMA-003 | Tipo soportado cumple requisitos Google | PASS: propiedades/políticas vigentes; FAIL: inelegible | MEDIA | OFICIAL | YES |
| SEO-SCHEMA-004 | `BreadcrumbList` coincide con UI | PASS: orden/URLs equivalentes; FAIL: discrepancia | MEDIA | OFICIAL | PARTIAL |
| SEO-SCHEMA-005 | Reviews no son autocontroladas/copias inválidas | PASS: elegibles y visibles; FAIL: markup abusivo | ALTA | OFICIAL | PARTIAL |
| SEO-SCHEMA-006 | No se promete rich result por schema válido | PASS: lenguaje de elegibilidad; FAIL: garantía | MEDIA | OFICIAL | NO |
| SEO-SCHEMA-007 | `sameAs` enlaza identidades equivalentes | PASS: perfiles oficiales inequívocos; FAIL: enlaces temáticos genéricos | MEDIA | OFICIAL | PARTIAL |
| SEO-SCHEMA-008 | FAQPage no se implementa por rich result Google | PASS: uso semántico justificado; WARNING: expectativa obsoleta | BAJA | OFICIAL | YES |
| SEO-CWV-001 | LCP de campo p75 ≤2.5 s | PASS: umbral por origen/URL disponible; FAIL: >4 s; WARNING: intermedio | MEDIA | OFICIAL | YES |
| SEO-CWV-002 | INP de campo p75 ≤200 ms | PASS: ≤200 ms; FAIL: >500 ms; WARNING: intermedio | MEDIA | OFICIAL | YES |
| SEO-CWV-003 | CLS de campo p75 ≤0.10 | PASS: ≤0.10; FAIL: >0.25; WARNING: intermedio | MEDIA | OFICIAL | YES |
| SEO-CWV-004 | Laboratorio y campo están etiquetados | PASS: origen/ventana/métrica explícitos; FAIL: mezcla causal | MEDIA | OFICIAL | YES |
| SEO-CWV-005 | Regresión de plantillas tiene presupuesto | PASS: umbrales CI/contexto; WARNING: sin control | MEDIA | CONSENSO PROFESIONAL | YES |
| SEO-MOBILE-001 | Viewport responsive correcto | PASS: viewport y layout usable; FAIL: página fija/inusable | ALTA | OFICIAL | YES |
| SEO-MOBILE-002 | Paridad móvil de contenido y metadata | PASS: equivalencia; FAIL: contenido/enlaces/schema ausentes | ALTA | OFICIAL | PARTIAL |
| SEO-MOBILE-003 | Controles táctiles utilizables | PASS: sin solapes y tamaño/espacio adecuados; WARNING: fallos | MEDIA | OFICIAL | PARTIAL |
| SEO-A11Y-001 | Imágenes tienen alternativa apropiada | PASS: alt útil/vacío según función; FAIL: barrera material | MEDIA | OFICIAL | PARTIAL |
| SEO-A11Y-002 | Formularios tienen labels/nombres | PASS: controles identificables; FAIL: sin nombre accesible | MEDIA | OFICIAL | YES |
| SEO-A11Y-003 | Sitio operable con teclado | PASS: foco/orden/acciones funcionales; FAIL: bloqueo | ALTA | OFICIAL | PARTIAL |
| SEO-A11Y-004 | HTML semántico precede ARIA | PASS: roles nativos o ARIA correcta; WARNING: abuso/conflicto | MEDIA | OFICIAL | PARTIAL |
| SEO-LINK-001 | Enlaces pagados se califican | PASS: `rel=sponsored`/`nofollow` apropiado; FAIL: manipulación | ALTA | OFICIAL | PARTIAL |
| SEO-LINK-002 | UGC está moderado/calificado | PASS: controles según riesgo; FAIL: spam indexable/enlaces manipulados | ALTA | OFICIAL | PARTIAL |
| SEO-LINK-003 | No hay PBN/paquetes/intercambios excesivos | PASS: adquisición editorial; FAIL: patrón manipulador | ALTA | OFICIAL | NO |
| SEO-LOCAL-001 | GBP representa negocio elegible y real | PASS: cumple guidelines; FAIL: virtual/falso/duplicado | CRÍTICA | OFICIAL | NO |
| SEO-LOCAL-002 | Nombre GBP es el nombre real | PASS: sin keywords añadidas; FAIL: keyword stuffing | ALTA | OFICIAL | PARTIAL |
| SEO-LOCAL-003 | Categoría primaria describe actividad principal | PASS: opción más específica real; FAIL: categoría irrelevante | ALTA | OFICIAL | NO |
| SEO-LOCAL-004 | Datos operativos están actualizados | PASS: dirección/área/teléfono/horarios/web correctos; FAIL: inconsistencia material | ALTA | OFICIAL | PARTIAL |
| SEO-LOCAL-005 | Reseñas no usan incentivo ni gating | PASS: solicitud neutral; FAIL: manipulación | ALTA | OFICIAL | NO |
| SEO-LOCAL-006 | Landing de ubicación es única y real | PASS: operación/contenido diferencial; FAIL: doorway clonada | ALTA | OFICIAL | NO |
| SEO-ENTITY-001 | Identidad de organización es consistente | PASS: nombre, URL, logo y perfiles convergen; WARNING: contradicciones | MEDIA | CONSENSO PROFESIONAL | PARTIAL |
| SEO-ENTITY-002 | `sameAs` no se usa como lista de backlinks | PASS: solo identidad equivalente; FAIL: enlaces no identitarios | MEDIA | OFICIAL | YES |
| SEO-AI-001 | Contenido es accesible al bot de búsqueda elegido | PASS: política y acceso deliberados; FAIL: bloqueo accidental | MEDIA | OFICIAL | YES |
| SEO-AI-002 | GPTBot se controla separadamente de OAI-SearchBot | PASS: decisión separada/documentada; WARNING: confusión | MEDIA | OFICIAL | YES |
| SEO-AI-003 | Medición distingue mención, cita, impresión, clic y conversión | PASS: métricas separadas; FAIL: equivalencia falsa | MEDIA | OFICIAL | NO |
| SEO-AI-004 | Hechos importantes son claros y trazables | PASS: fuente/fecha/contexto; WARNING: afirmaciones ambiguas | MEDIA | EVIDENCIA MODERADA | PARTIAL |
| SEO-AI-005 | No se exige markup especial para AI Overviews | PASS: fundamentos/schema aplicable; WARNING: markup inventado | BAJA | OFICIAL | YES |
| SEO-AI-006 | `llms.txt` se trata como experimento | PASS: no requisito y medición definida; FAIL: promesa de visibilidad | EXPERIMENTAL | OFICIAL | YES |

Estas reglas detectan síntomas; el informe debe agruparlos por causa raíz. Por ejemplo, miles de URLs no canónicas en sitemap constituyen un problema de generación de sitemap, no miles de tareas independientes.

---

## 28. Qué NO debe automatizarse completamente

| Tarea | Por qué requiere juicio | Rol seguro de la automatización |
|---|---|---|
| Intención de búsqueda | Una misma consulta puede tener tareas, etapas y audiencias distintas. | Agrupar SERPs/consultas y presentar muestras; una persona decide. |
| Utilidad y satisfacción | No se reduce a longitud, legibilidad o entidades contadas. | Detectar huecos, duplicación y feedback; revisión de tarea real. |
| Experiencia de primera mano | Fotos, pruebas o biografías pueden falsificarse. | Señalar ausencia/inconsistencia; verificar evidencia y proceso. |
| Expertise | Depende del ámbito, precisión y consecuencias del consejo. | Comprobar credenciales declaradas y fuentes; no “puntuar E-E-A-T”. |
| Originalidad | La similitud textual no detecta síntesis, datos o perspectiva nuevos. | Comparar corpus y fuentes; un experto evalúa aporte. |
| Confianza/reputación | Contexto, gravedad y actualidad de menciones importan. | Recopilar evidencia y fechas; no asignar verdad por sentimiento. |
| Diferenciación competitiva | Requiere producto, marca y economía, no solo SERP. | Inventariar formatos/temas; estrategia humana. |
| Naturalidad de anchors/copy | Las reglas simples producen falsos positivos culturales y lingüísticos. | Detectar patrones extremos; revisión editorial. |
| Decisión canonical | La equivalencia semántica y el objetivo de negocio pueden no ser observables. | Señalar conflictos técnicos; propietario decide agrupación. |
| Redirect de contenido eliminado | “Equivalente” exige entender expectativa y valor histórico. | Sugerir candidatos por similitud; aprobación humana. |
| Calidad de una página local | Dirección, servicio, comunidad y diferencias deben ser auténticos. | Detectar clones/NAP; validación local. |
| Categorías y servicios GBP | La categoría más cercana puede no representar el negocio o ser inelegible. | Mostrar opciones/cambios; decisión del operador. |
| Respuestas a reseñas | Privacidad, empatía y riesgo legal no admiten publicación ciega. | Borrador y triage; revisión antes de enviar. |
| Evaluación de enlaces | Métricas externas no determinan manipulación ni valor editorial. | Priorizar patrones; investigación manual. |
| Declaraciones YMYL | Exactitud médica, legal o financiera exige especialista y vigencia. | Detectar claims/fuentes/fechas; aprobación experta. |
| Contenido generado por IA | Un score de detector no prueba autoría ni calidad. | QA factual, enlaces y duplicación; editor responsable. |
| Citabilidad en IA | Las respuestas varían por modelo, tiempo, query y recuperación. | Pruebas repetidas y registro; no declarar causalidad. |
| Priorización final | Impacto, alcance, riesgo y esfuerzo son propios del proyecto. | Calcular escenario y confianza; responsable acepta prioridad. |

**Prohibición operativa:** ningún agente debe desindexar, redirigir masivamente, borrar contenido, cambiar robots/canonicals, publicar schema/reseñas ni adquirir/desautorizar enlaces solo porque una regla automática falló. Exigir muestra, causa raíz, rollback, propietario y validación.

---

## 29. Minimum SEO Baseline

Especificación de aceptación para una web nueva. `MUST` bloquea producción salvo excepción escrita; `SHOULD` requiere justificación si se omite; `COULD` es opcional y medible.

### MUST

- [ ] DNS, HTTPS, certificado, redirección de host/protocolo y disponibilidad funcionan en producción.
- [ ] Producción no hereda autenticación, `Disallow: /`, `noindex` ni canonicals de staging.
- [ ] Cada URL pública responde con estado semántico correcto: 200, 3xx, 404/410 o 5xx.
- [ ] URLs inexistentes no devuelven SPA/plantilla vacía con 200.
- [ ] `robots.txt` es accesible, válido y enlaza sitemaps pertinentes.
- [ ] Sitemap XML contiene solo URLs canónicas, 200 e indexables y respeta límites.
- [ ] Cada página objetivo es accesible mediante enlaces `<a href>` desde una ruta rastreable.
- [ ] Cada página objetivo tiene canonical única, absoluta, coherente y hacia una URL 200 indexable.
- [ ] Redirecciones no forman loops y los cambios permanentes llegan al equivalente final.
- [ ] Cada plantilla indexable entrega contenido principal y enlaces críticos en render comprobable.
- [ ] Deep links JavaScript cargan directamente; metadata/robots/canonical son correctos por ruta.
- [ ] Cada página indexable tiene `<title>` descriptivo, heading/contexto y contenido real para su intención.
- [ ] Imágenes informativas tienen alternativa; formularios tienen labels; navegación esencial funciona con teclado.
- [ ] Layout móvil, viewport, zoom, contenido, enlaces, metadata y schema mantienen paridad.
- [ ] Datos estructurados, si existen, son válidos, visibles, veraces y cumplen políticas aplicables.
- [ ] No se publican doorway pages, keyword stuffing, schema engañoso, contenido masivo sin valor ni enlaces manipulados.
- [ ] Sitio protege datos/administración, aplica parches y tiene monitor de uptime, 5xx, TLS y seguridad.
- [ ] GSC (preferiblemente propiedad de dominio) y Bing Webmaster Tools están verificados por propietarios autorizados.
- [ ] Analytics/consentimiento, si se usan, funcionan sin bloquear contenido esencial y respetan normativa aplicable.
- [ ] Existe plan documentado de rollback para URLs, robots, canonicals, redirects y renderizado.

### SHOULD

- [ ] Arquitectura refleja servicios/temas/ubicaciones reales y evita huérfanas/facetas infinitas.
- [ ] Breadcrumbs visibles y `BreadcrumbList` coherente apoyan jerarquía donde aplica.
- [ ] Titles, descriptions, H1/contexto, anchors e imágenes se generan con controles por plantilla.
- [ ] Content briefs documentan audiencia, intención, evidencia, responsable y fecha de revisión.
- [ ] Organization/LocalBusiness y otros tipos soportados se implementan solo donde describen contenido real.
- [ ] Presupuesto de performance prueba plantillas críticas en móvil; CWV se monitoriza con campo cuando haya datos.
- [ ] Objetivo de campo: LCP p75 ≤2.5 s, INP p75 ≤200 ms y CLS p75 ≤0.10.
- [ ] Imágenes están dimensionadas, comprimidas, responsive y el recurso LCP se prioriza.
- [ ] Accesibilidad se prueba con herramientas y teclado/lector de pantalla en flujos críticos.
- [ ] Logs, releases y migraciones permiten correlacionar cambios con rastreo/visibilidad.
- [ ] GBP, si aplica, cumple elegibilidad, datos reales, categoría y horarios; no hay duplicados.
- [ ] Perfiles oficiales, NAP, nombre, logo y `sameAs` representan una entidad consistente.
- [ ] Política editorial contempla IA, revisión humana, fuentes, correcciones y contenido programático.
- [ ] Política de bots distingue búsqueda, entrenamiento, agentes y necesidades de negocio.
- [ ] Se define dashboard base de GSC/analytics/conversiones y responsables de alertas.

### COULD

- [ ] Añadir schema soportado adicional cuando habilite una presentación útil y sea mantenible.
- [ ] Crear feeds/APIs/datos estructurados adicionales para integraciones reales.
- [ ] Experimentar con `llms.txt` solo si existe consumidor identificado, hipótesis y medición.
- [ ] Medir citas/menciones en sistemas de IA separadas de clics y conversiones.
- [ ] Automatizar reglas `YES` en CI y muestreo `PARTIAL` en observabilidad.
- [ ] Ejecutar experimentos SEO controlados con hipótesis, ventana, guardrails y registro.

### Criterio de liberación

```text
GO: todos los MUST aplicables = PASS; excepciones firmadas con propietario, caducidad y rollback.
NO-GO: cualquier MUST CRÍTICO/ALTO = FAIL sin mitigación verificada.
CONDITIONAL GO: WARNING documentado, impacto acotado, monitor y fecha de corrección.
```

---

## 30. SEO 2026: las 20 cosas que realmente importan

Orden basado en evidencia, impacto, universalidad, riesgo y beneficio; no en popularidad.

1. **Mantener acceso seguro y estable.** DNS, TLS, servidor, WAF y 5xx preceden a toda optimización. [OFICIAL]
2. **No bloquear ni excluir por accidente.** Robots, `noindex` y headers pueden borrar la elegibilidad de un sitio. [OFICIAL]
3. **Servir estados HTTP honestos.** Diferenciar éxito, redirect, ausencia y error evita soft 404 y trampas. [OFICIAL]
4. **Hacer rastreables contenido y enlaces esenciales.** HTML/enlaces accesibles y render fiable reducen dependencia y fallos. [OFICIAL]
5. **Resolver intención con contenido genuinamente útil.** No hay sustituto técnico para satisfacer la tarea del usuario. [OFICIAL]
6. **Consolidar duplicados coherentemente.** Redirect, canonical, sitemap e internos deben señalar la misma versión. [OFICIAL]
7. **Diseñar arquitectura navegable, no un inventario de keywords.** Hubs, categorías y páginas locales deben representar oferta real. [OFICIAL/CONSENSO PROFESIONAL]
8. **Construir confianza demostrable.** Exactitud, fuentes, responsables, experiencia y políticas importan más que “optimizar E-E-A-T”. [OFICIAL]
9. **Evitar spam y sobreoptimización.** Escala sin valor, doorway pages, enlaces pagados, stuffing y schema falso elevan riesgo. [OFICIAL]
10. **Preservar URLs y planificar migraciones.** Mapas 1:1, redirects y monitorización protegen señales acumuladas. [OFICIAL]
11. **Usar Search Console, logs y muestras para diagnosticar.** Separar descubrimiento, crawl, render, indexación, ranking y demanda. [OFICIAL]
12. **Mantener paridad móvil.** Google usa la versión móvil para indexar; contenido/metadata/schema no deben degradarse. [OFICIAL]
13. **Optimizar rendimiento real sin convertirlo en culto al score.** CWV mejora UX y participa en page experience, pero no domina ranking. [OFICIAL]
14. **Hacer contenido comprensible y citable.** Estructura clara, hechos trazables, entidades consistentes y fuentes ayudan a usuarios y recuperación. [OFICIAL/EVIDENCIA MODERADA]
15. **Implementar structured data veraz y soportado.** Distinguir validación Schema.org, soporte Google y elegibilidad para rich result. [OFICIAL]
16. **Ganar autoridad editorial, no métricas.** Enlaces/menciones relevantes son valiosos; DA/DR/AS no son métricas Google. [OFICIAL]
17. **Para local, operar bien y representar la realidad.** Elegibilidad GBP, categoría, relevancia, distancia, prominencia y reseñas auténticas. [OFICIAL]
18. **Tratar IA como capa adicional de recuperación y medición.** Fundamentos SEO siguen vigentes; controlar bots y medir citas/referrals por separado. [OFICIAL]
19. **Automatizar comprobaciones, no decisiones irreversibles.** CI detecta regresiones; intención, calidad, reputación y contexto necesitan juicio. [CONSENSO PROFESIONAL]
20. **Experimentar con etiquetas emergentes sin confundirlas con estándares.** GEO/AEO aportan marcos de medición; `llms.txt` sigue experimental y Google lo ignora. [OFICIAL/EXPERIMENTO]

---

## 31. Fuentes maestras

Solo se incluyen fuentes consultadas y utilizadas para este documento. “Consultado” no significa que toda afirmación de la fuente se acepte; los estudios observacionales se usan con sus límites.

### Fuentes oficiales

| ID | Nombre | Organización | Título | Fecha | URL | Tipo de evidencia |
|---|---|---|---|---|---|---|
| SRC-OFF-001 | Google Search Central | Google | How Search Works | Actualizado 2025-12-10 | [Enlace](https://developers.google.com/search/docs/fundamentals/how-search-works) | `OFICIAL` |
| SRC-OFF-002 | Google Search Central | Google | Search Essentials | Consultado 2026-08-24 | [Enlace](https://developers.google.com/search/docs/essentials) | `OFICIAL` |
| SRC-OFF-003 | Google Search Central | Google | SEO Starter Guide | Consultado 2026-08-24 | [Enlace](https://developers.google.com/search/docs/fundamentals/seo-starter-guide) | `OFICIAL` |
| SRC-OFF-004 | Google Search Central | Google | AI optimization guide | Actualizado 2026-07-10 | [Enlace](https://developers.google.com/search/docs/fundamentals/ai-optimization-guide) | `OFICIAL` |
| SRC-OFF-005 | Google Search Central | Google | Third-party SEO tools: guidance | Actualizado 2026-06-05 | [Enlace](https://developers.google.com/search/docs/fundamentals/third-party-seo) | `OFICIAL` |
| SRC-OFF-006 | Google Search Central | Google | Creating helpful, reliable, people-first content | Consultado 2026-08-24 | [Enlace](https://developers.google.com/search/docs/fundamentals/creating-helpful-content) | `OFICIAL` |
| SRC-OFF-007 | Google Search Central | Google | Guidance about AI-generated content | Consultado 2026-08-24 | [Enlace](https://developers.google.com/search/docs/fundamentals/using-gen-ai-content) | `OFICIAL` |
| SRC-OFF-008 | Google Search Central | Google | Spam policies for Google web search | Consultado 2026-08-24 | [Enlace](https://developers.google.com/search/docs/essentials/spam-policies) | `OFICIAL` |
| SRC-OFF-009 | Google Search Central | Google | Google Search's core updates | Consultado 2026-08-24 | [Enlace](https://developers.google.com/search/docs/appearance/core-updates) | `OFICIAL` |
| SRC-OFF-010 | Google Search Central | Google | Introduction to robots.txt | Actualizado 2025-12-10 | [Enlace](https://developers.google.com/search/docs/crawling-indexing/robots/intro) | `OFICIAL` |
| SRC-OFF-011 | Google Search Central | Google | Block Search indexing with `noindex` | Actualizado 2025-12-10 | [Enlace](https://developers.google.com/search/docs/crawling-indexing/block-indexing) | `OFICIAL` |
| SRC-OFF-012 | Google Search Central | Google | Robots meta tag, data-nosnippet and X-Robots-Tag | Consultado 2026-08-24 | [Enlace](https://developers.google.com/search/docs/crawling-indexing/robots-meta-tag) | `OFICIAL` |
| SRC-OFF-013 | Google Search Central | Google | Links Google can crawl | Consultado 2026-08-24 | [Enlace](https://developers.google.com/search/docs/crawling-indexing/links-crawlable) | `OFICIAL` |
| SRC-OFF-014 | Google Search Central | Google | Sitemaps overview | Consultado 2026-08-24 | [Enlace](https://developers.google.com/search/docs/crawling-indexing/sitemaps/overview) | `OFICIAL` |
| SRC-OFF-015 | Google Search Central | Google | Canonical URLs: consolidate duplicate URLs | Actualizado 2026-07-10 | [Enlace](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls) | `OFICIAL` |
| SRC-OFF-016 | Google Search Central | Google | Redirects and Google Search | Consultado 2026-08-24 | [Enlace](https://developers.google.com/search/docs/crawling-indexing/301-redirects) | `OFICIAL` |
| SRC-OFF-017 | Google Search Central | Google | Site moves with URL changes | Consultado 2026-08-24 | [Enlace](https://developers.google.com/search/docs/crawling-indexing/site-move-with-url-changes) | `OFICIAL` |
| SRC-OFF-018 | Google Search Central | Google | URL structure best practices | Consultado 2026-08-24 | [Enlace](https://developers.google.com/search/docs/crawling-indexing/url-structure) | `OFICIAL` |
| SRC-OFF-019 | Google Search Central | Google | Troubleshoot crawling errors | Consultado 2026-08-24 | [Enlace](https://developers.google.com/search/docs/crawling-indexing/troubleshoot-crawling-errors) | `OFICIAL` |
| SRC-OFF-020 | Google Search Central | Google | JavaScript SEO basics | Consultado 2026-08-24 | [Enlace](https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics) | `OFICIAL` |
| SRC-OFF-021 | Google Search Central | Google | Dynamic rendering as a workaround | Consultado 2026-08-24 | [Enlace](https://developers.google.com/search/docs/crawling-indexing/javascript/dynamic-rendering) | `OFICIAL` |
| SRC-OFF-022 | Google Search Central | Google | Mobile-first indexing best practices | Consultado 2026-08-24 | [Enlace](https://developers.google.com/search/docs/crawling-indexing/mobile/mobile-sites-mobile-first-indexing) | `OFICIAL` |
| SRC-OFF-023 | Google Search Central | Google | Influencing title links | Consultado 2026-08-24 | [Enlace](https://developers.google.com/search/docs/appearance/title-link) | `OFICIAL` |
| SRC-OFF-024 | Google Search Central | Google | Control snippets in search results | Consultado 2026-08-24 | [Enlace](https://developers.google.com/search/docs/appearance/snippet) | `OFICIAL` |
| SRC-OFF-025 | Google Search Central | Google | Google Images SEO best practices | Consultado 2026-08-24 | [Enlace](https://developers.google.com/search/docs/appearance/google-images) | `OFICIAL` |
| SRC-OFF-026 | Google Search Central | Google | Understanding page experience | Consultado 2026-08-24 | [Enlace](https://developers.google.com/search/docs/appearance/page-experience) | `OFICIAL` |
| SRC-OFF-027 | Google Search Central | Google | Search Gallery: structured data features | Consultado 2026-08-24 | [Enlace](https://developers.google.com/search/docs/appearance/structured-data/search-gallery) | `OFICIAL` |
| SRC-OFF-028 | Google Search Central | Google | Introduction to structured data markup | Consultado 2026-08-24 | [Enlace](https://developers.google.com/search/docs/appearance/structured-data/intro-structured-data) | `OFICIAL` |
| SRC-OFF-029 | Google Search Central | Google | Structured data general guidelines | Consultado 2026-08-24 | [Enlace](https://developers.google.com/search/docs/appearance/structured-data/sd-policies) | `OFICIAL` |
| SRC-OFF-030 | Google Search Central | Google | Organization structured data | Consultado 2026-08-24 | [Enlace](https://developers.google.com/search/docs/appearance/structured-data/organization) | `OFICIAL` |
| SRC-OFF-031 | Google Search Central | Google | Local business structured data | Consultado 2026-08-24 | [Enlace](https://developers.google.com/search/docs/appearance/structured-data/local-business) | `OFICIAL` |
| SRC-OFF-032 | Google Search Central | Google | Breadcrumb structured data | Consultado 2026-08-24 | [Enlace](https://developers.google.com/search/docs/appearance/structured-data/breadcrumb) | `OFICIAL` |
| SRC-OFF-033 | Google Search Central | Google | Article structured data | Consultado 2026-08-24 | [Enlace](https://developers.google.com/search/docs/appearance/structured-data/article) | `OFICIAL` |
| SRC-OFF-034 | Google Search Central | Google | Product structured data | Consultado 2026-08-24 | [Enlace](https://developers.google.com/search/docs/appearance/structured-data/product) | `OFICIAL` |
| SRC-OFF-035 | Google Search Central | Google | Review snippet structured data | Consultado 2026-08-24 | [Enlace](https://developers.google.com/search/docs/appearance/structured-data/review-snippet) | `OFICIAL` |
| SRC-OFF-036 | Google Search Central | Google | Event structured data | Consultado 2026-08-24 | [Enlace](https://developers.google.com/search/docs/appearance/structured-data/event) | `OFICIAL` |
| SRC-OFF-037 | Google Search Central | Google | Course list structured data | Consultado 2026-08-24 | [Enlace](https://developers.google.com/search/docs/appearance/structured-data/course) | `OFICIAL` |
| SRC-OFF-038 | Search Console Help | Google | Search Console reports overview | Consultado 2026-08-24 | [Enlace](https://support.google.com/webmasters/answer/7451491) | `OFICIAL` |
| SRC-OFF-039 | Search Console Help | Google | Performance report | Consultado 2026-08-24 | [Enlace](https://support.google.com/webmasters/answer/7576553) | `OFICIAL` |
| SRC-OFF-040 | Search Console Help | Google | Page Indexing report | Consultado 2026-08-24 | [Enlace](https://support.google.com/webmasters/answer/7440203) | `OFICIAL` |
| SRC-OFF-041 | Search Console Help | Google | URL Inspection tool | Consultado 2026-08-24 | [Enlace](https://support.google.com/webmasters/answer/9012289) | `OFICIAL` |
| SRC-OFF-042 | Search Console Help | Google | Generative AI performance report | Despliegue 2026; consultado 2026-08-24 | [Enlace](https://support.google.com/webmasters/answer/16984139) | `OFICIAL` |
| SRC-OFF-043 | Search Console Help | Google | Data anomalies in Search Console | Actualizado 2026-08 | [Enlace](https://support.google.com/webmasters/answer/6211453) | `OFICIAL` |
| SRC-OFF-044 | Google Search Central | Google | Debugging drops in Search traffic | Consultado 2026-08-24 | [Enlace](https://developers.google.com/search/docs/monitor-debug/debugging-search-traffic-drops) | `OFICIAL` |
| SRC-OFF-045 | Search Status Dashboard | Google | Google Search Status Dashboard | Consultado 2026-08-24 | [Enlace](https://status.search.google.com/summary) | `OFICIAL` |
| SRC-OFF-046 | web.dev | Google/Chrome | Defining Core Web Vitals thresholds | Actualizado 2025-05-07 | [Enlace](https://web.dev/articles/defining-core-web-vitals-thresholds) | `OFICIAL` |
| SRC-OFF-047 | web.dev | Google/Chrome | Web Vitals | Consultado 2026-08-24 | [Enlace](https://web.dev/articles/vitals) | `OFICIAL` |
| SRC-OFF-048 | web.dev | Google/Chrome | Time to First Byte (TTFB) | Consultado 2026-08-24 | [Enlace](https://web.dev/articles/ttfb) | `OFICIAL` |
| SRC-OFF-049 | web.dev | Google/Chrome | First Contentful Paint (FCP) | Consultado 2026-08-24 | [Enlace](https://web.dev/articles/fcp) | `OFICIAL` |
| SRC-OFF-050 | Chrome for Developers | Google/Chrome | Chrome UX Report API | Consultado 2026-08-24 | [Enlace](https://developer.chrome.com/docs/crux/api) | `OFICIAL` |
| SRC-OFF-051 | PageSpeed Insights | Google | About PageSpeed Insights | Consultado 2026-08-24 | [Enlace](https://developers.google.com/speed/docs/insights/v5/about) | `OFICIAL` |
| SRC-OFF-052 | Chrome for Developers | Google/Chrome | Lighthouse overview | Actualizado 2025-06-02 | [Enlace](https://developer.chrome.com/docs/lighthouse/overview) | `OFICIAL` |
| SRC-OFF-053 | web.dev | Google/Chrome | Why lab and field data can be different | Consultado 2026-08-24 | [Enlace](https://web.dev/articles/lab-and-field-data-differences) | `OFICIAL` |
| SRC-OFF-054 | web.dev | Google/Chrome | Building agent-friendly websites | 2026 | [Enlace](https://web.dev/articles/ai-agent-site-ux) | `OFICIAL` como guía técnica; no factor confirmado |
| SRC-OFF-055 | Schema.org | Schema.org Community Group | Schema.org release 30.0 | 2026-03-19 | [Enlace](https://schema.org/version/latest) | `OFICIAL` del vocabulario |
| SRC-OFF-056 | Schema Markup Validator | Schema.org | Validator | Consultado 2026-08-24 | [Enlace](https://validator.schema.org/) | `OFICIAL` del vocabulario |
| SRC-OFF-057 | Rich Results Test | Google | Rich Results Test | Consultado 2026-08-24 | [Enlace](https://search.google.com/test/rich-results) | `OFICIAL` de elegibilidad técnica Google |
| SRC-OFF-058 | Google Business Profile Help | Google | Tips to improve local ranking | Consultado 2026-08-24 | [Enlace](https://support.google.com/business/answer/7091) | `OFICIAL` |
| SRC-OFF-059 | Google Business Profile Help | Google | Guidelines for representing your business | Consultado 2026-08-24 | [Enlace](https://support.google.com/business/answer/3038177) | `OFICIAL` |
| SRC-OFF-060 | Google Business Profile Help | Google | Choose a business category | Consultado 2026-08-24 | [Enlace](https://support.google.com/business/answer/7249669) | `OFICIAL` |
| SRC-OFF-061 | Bing Webmaster Guidelines | Microsoft | Webmaster Guidelines | Consultado 2026-08-24 | [Enlace](https://www.bing.com/webmasters/help/webmaster-guidelines-30fba23a) | `OFICIAL` |
| SRC-OFF-062 | Bing Webmaster Blog | Microsoft | Introducing AI Performance in Bing Webmaster Tools | 2026-02 | [Enlace](https://blogs.bing.com/webmaster/February-2026/Introducing-AI-Performance-in-Bing-Webmaster-Tools-Public-Preview) | `OFICIAL` |
| SRC-OFF-063 | OpenAI Developers | OpenAI | Crawlers and user agents | Consultado 2026-08-24 | [Enlace](https://developers.openai.com/api/docs/bots) | `OFICIAL` |
| SRC-OFF-064 | OpenAI Help Center | OpenAI | Publishers and developers FAQ | Consultado 2026-08-24 | [Enlace](https://help.openai.com/en/articles/12627856-publishers-and-developers-faq) | `OFICIAL` |
| SRC-OFF-065 | Perplexity Docs | Perplexity | Perplexity crawlers | Consultado 2026-08-24 | [Enlace](https://docs.perplexity.ai/docs/resources/perplexity-crawlers) | `OFICIAL` |
| SRC-OFF-066 | WCAG 2.2 Quick Reference | W3C WAI | How to Meet WCAG 2.2 | Consultado 2026-08-24 | [Enlace](https://www.w3.org/WAI/WCAG22/quickref/) | `OFICIAL` del estándar |
| SRC-OFF-067 | WAI Tutorials | W3C WAI | Page Structure: Headings | Consultado 2026-08-24 | [Enlace](https://www.w3.org/WAI/tutorials/page-structure/headings/) | `OFICIAL` del estándar |

### Estudios y datasets

| ID | Nombre | Organización | Título / muestra | Fecha | URL | Tipo de evidencia |
|---|---|---|---|---|---|---|
| SRC-DATA-001 | Ahrefs Research | Ahrefs | AI Overview citations vs organic top 10; 863k SERPs y 4M URLs | 2026-03-02 | [Enlace](https://ahrefs.com/blog/ai-overview-citations-top-10/) | `EVIDENCIA MODERADA`; observacional |
| SRC-DATA-002 | Ahrefs Research | Ahrefs | Brand correlations with AI Overview mentions; 75k marcas | 2026 | [Enlace](https://ahrefs.com/blog/ai-overview-brand-correlation/) | `EVIDENCIA MODERADA`; correlación |
| SRC-DATA-003 | Ahrefs Research | Ahrefs | AI Overview citation volatility between updates | 2026 | [Enlace](https://ahrefs.com/blog/ai-overview-change/) | `EVIDENCIA MODERADA`; observacional |
| SRC-DATA-004 | Ahrefs Research | Ahrefs | Do AI Overviews reduce clicks? | 2025, actualizado 2026 | [Enlace](https://ahrefs.com/blog/ai-overviews-reduce-clicks/) | `EVIDENCIA MODERADA`; CTR observacional |
| SRC-DATA-005 | Ahrefs Research | Ahrefs | Search traffic study and referring-domain correlations | Consultado 2026-08-24 | [Enlace](https://ahrefs.com/blog/search-traffic-study/) | `EVIDENCIA MODERADA`; correlación |
| SRC-DATA-006 | Semrush Research | Semrush | AI Overviews study; más de 10M keywords | 2025-12 | [Enlace](https://www.semrush.com/blog/semrush-ai-overviews-study/) | `EVIDENCIA MODERADA`; muestra propietaria |
| SRC-DATA-007 | SISTRIX Research | SISTRIX | AI Overviews in Germany: prevalence and CTR modelling | 2026-02 | [Enlace](https://www.sistrix.com/blog/ai-overviews-in-germany/) | `EVIDENCIA MODERADA`; mercado/modelo limitado |
| SRC-DATA-008 | Local Consumer Review Survey | BrightLocal | Consumer review behaviour survey | 2026 | [Enlace](https://www.brightlocal.com/research/local-consumer-review-survey/) | `EVIDENCIA MODERADA`; conducta, no ranking |
| SRC-DATA-009 | GEO | Princeton/Georgia Tech/Allen Institute/IIT Delhi | Generative Engine Optimization, KDD 2024 | 2024 | [Enlace](https://dl.acm.org/doi/10.1145/3637528.3671900) | `EXPERIMENTO`; benchmark limitado |
| SRC-DATA-010 | GEO critical survey | Investigación académica | Generative Engine Optimization: a critical survey | 2026-07 | [Enlace](https://arxiv.org/html/2607.14035v1) | `EXPERIMENTO`/revisión crítica |
| SRC-DATA-011 | Wikipedia traffic/AIO | Investigación académica | Causal estimate of AI Overview exposure on Wikipedia traffic | 2026-02 | [Enlace](https://arxiv.org/abs/2602.18455) | `EVIDENCIA MODERADA/FUERTE` dentro de su diseño; no universal |

### Especialistas y análisis

| ID | Nombre | Organización | Título | Fecha | URL | Tipo de evidencia |
|---|---|---|---|---|---|---|
| SRC-EXP-001 | Darren Shaw y 47 especialistas | Whitespark | Local Search Ranking Factors 2026 | Publicado 2025-11-06; edición 2026 | [Enlace](https://whitespark.ca/local-search-ranking-factors/) | `CONSENSO PROFESIONAL`; encuesta, no pesos Google |
| SRC-EXP-002 | Jeremy Howard / Answer.AI | llmstxt.org | The `/llms.txt` file proposal | Propuesta 2024-09; actualizada 2026-08-10 | [Enlace](https://llmstxt.org/) | `HIPÓTESIS`/propuesta emergente |
| SRC-EXP-003 | Answer.AI community | GitHub | `AnswerDotAI/llms-txt` specification and discussion | Consultado 2026-08-24 | [Enlace](https://github.com/AnswerDotAI/llms-txt) | `HIPÓTESIS`/adopción comunitaria |

### Política de revisión de fuentes

- Revisar trimestralmente fechas, changelogs y documentación de features.
- Antes de afirmar que Google “usa” una señal, exigir fuente oficial o etiquetar la inferencia.
- Antes de generalizar un estudio, registrar mercado, idioma, muestra, periodo y metodología.
- Archivar cambios de umbrales, políticas, rich results y reports con fecha efectiva.
- Degradar a `SIN EVIDENCIA SUFICIENTE` cualquier afirmación cuya fuente desaparezca o no sea reproducible.
