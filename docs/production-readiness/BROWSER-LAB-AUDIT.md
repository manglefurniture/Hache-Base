# P1-03 — Lighthouse y accesibilidad automática

P1-03 incorpora una auditoría de navegador reproducible sobre páginas y estados de Critical User Flow (CUF) controlados por Hache Base. El objetivo es detectar regresiones tempranas de performance y accesibilidad automática con presupuestos versionados, sin convertir una medición de laboratorio en evidencia de campo o en aprobación manual de accesibilidad.

## Contrato versionado

La fuente de verdad operativa está en `tests/browser/budgets.json`:

- herramienta fijada: `@lhci/cli@0.15.1`;
- perfil: móvil simulado;
- tres ejecuciones por URL para reducir ruido de laboratorio;
- fixture público mínimo: `/index.html`;
- estado CUF de validación: `/form-error.html`;
- accesibilidad Lighthouse: score `1.0` como bloqueo;
- performance agregada: score `0.90` solo como advertencia diagnóstica;
- LCP: máximo `2500 ms`;
- CLS: máximo `0.1`;
- TBT como proxy de interactividad de laboratorio: máximo `300 ms`.

Los límites concretos de LCP/CLS/TBT sí son budgets de regresión del fixture. El score agregado de Lighthouse no sustituye métricas concretas ni datos de campo y, por diseño, no bloquea el pipeline.

## Ejecución en CI

El job `browser_audit` del workflow normal:

1. usa Node 22;
2. instala exactamente la versión declarada de Lighthouse CI;
3. valida primero el contrato con `tests/browser/config-contract.mjs`;
4. ejecuta `lhci autorun --config=tests/browser/lighthouserc.cjs`;
5. conserva los reportes JSON/HTML como artefacto de GitHub Actions.

La configuración usa el servidor estático interno de Lighthouse CI y no depende de APIs, CDNs, fuentes o assets remotos.

## Qué demuestra

Un resultado verde demuestra que el fixture versionado de Hache Base continúa dentro de los budgets automáticos configurados y que Lighthouse no detecta fallos automáticos de accesibilidad en esas páginas/estados.

Sirve como regresión temprana del Core y como patrón reutilizable para proyectos derivados.

## Qué NO demuestra

Un resultado verde **no** significa que un proyecto derivado sea Production Ready y no debe transformar automáticamente controles del Standard a `PASS`.

En particular:

- no satisface `PERF-001`, porque Core no puede producir p75 de campo de un proyecto real;
- no sustituye `PERF-002` del proyecto: el proyecto debe medir su build/artefacto representativo y conservar su propio reporte;
- no sustituye pruebas manuales A11Y de teclado, foco, zoom/reflow, lector de pantalla, contenido, errores ni CUF reales;
- no demuestra comportamiento detrás de Nginx/Apache, CDN, proxy, autenticación, datos reales o integraciones de terceros;
- no cubre desktop ni condiciones específicas de cada proyecto salvo que el proyecto las agregue explícitamente.

La automatización de Lighthouse es evidencia complementaria. Los controles con revisión humana continúan requiriendo persona revisora y evidencia del proyecto.

## Adopción por proyecto

Un proyecto derivado debe reutilizar el patrón, no los resultados del fixture. Como mínimo debe:

- apuntar a páginas y CUF representativos del build de producción;
- definir budgets justificados y versionados;
- registrar commit/artefacto, entorno, herramienta y versión;
- incluir móvil limitado y añadir desktop cuando corresponda;
- conservar reportes de CI;
- investigar regresiones de métricas concretas aunque el score agregado permanezca aceptable;
- mantener separada la evidencia automática de la revisión manual de accesibilidad.

P1-03 no incorpora RUM/Web Vitals de campo; eso pertenece al siguiente alcance del roadmap.
