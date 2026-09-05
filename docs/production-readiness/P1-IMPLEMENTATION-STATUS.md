# Production Readiness P1 — estado de implementación

> Estado documental de Hache Base después de completar los ítems P1-01…P1-11 del roadmap. Este documento **no** modifica el Standard, la Checklist ni los criterios de salida del roadmap y no declara Production Ready a ningún proyecto derivado.

## Corte

- Fecha: 2026-09-05
- `main` verificado: `1b1f38f7ade766e39a304a292ba68009430ec9f8`
- Fuente normativa: `PRODUCTION-READINESS-STANDARD.md` v1.1
- Secuencia: `PRODUCTION-READINESS-ROADMAP.md`

## Baseline P1 implementado en Hache Base

| Ítem | Implementación reusable | PR principal / follow-up |
| --- | --- | --- |
| P1-01 | Reporte CI de readiness por nivel desde el registro canónico, sin auto-PASS ni sustitución de revisión humana. | #22, #23, #25 |
| P1-02 | Fixture HTTP real para headers, cookies, cache, compresión, status, redirects, 404/500 y CSP report-only. | #24 |
| P1-03 | Lighthouse CI y accesibilidad con versiones/budgets reproducibles y evidencia de CI. | #26 |
| P1-04 | RUM/Web Vitals opt-in, minimizado y vendor-neutral con agregación p75 y límites de evidencia. | #27, #28 |
| P1-05 | Inventario de terceros con owner, datos, timeout/fallback, coste medido y criterio de retiro. | #29 |
| P1-06 | Matriz reusable de cache/invalidation y regresiones HTTP de validators/private/no-store/immutable. | #30, #31 |
| P1-07 | Formulario fixture Nivel B con validación servidor, CSRF, rate limit de fixture, honeypot, dedupe y estados accesibles. | #32 |
| P1-08 | Extension opt-in de estado de email/webhooks con dedupe, firma, ordering y reprocess. | #33 |
| P1-09 | Inventario de datos/privacidad, retención/eliminación, derechos, trackers y estados cero verificables. | #34 |
| P1-10 | Artifact promotion build/test once con commit+SHA-256 verificables, snapshot de promoción y rollback sin rebuild. | #35 |
| P1-11 | Budgets automatizables de release/assets/imágenes/fuentes/terceros con límites por proyecto y evidencia Lighthouse. | #36 |

Los ítems anteriores están disponibles como primitives, Extensions, plantillas, fixtures o tests de Hache Base. Su mera existencia **no** convierte los controles relacionados en PASS para un proyecto derivado.

## Estado del criterio de salida P1

El roadmap exige tres condiciones para cerrar P1:

1. CI produce un reporte legible y no declara pruebas humanas inexistentes — **cubierto en Hache Base** por P1-01 y sus regresiones.
2. Fixtures A/B/C cubren headers, errores, CUF y budgets — **baseline reusable implementado**, con fixtures/tests distribuidos entre P1-02, P1-03, P1-06, P1-07 y P1-11; la evidencia final sigue siendo del proyecto/entorno que adopta esos contratos.
3. Al menos un proyecto B/C piloto produce evidencia de campo, restore y comunicación status — **PENDIENTE DE EVIDENCIA DE PROYECTO**.

Por tanto:

- **P1-01…P1-11: IMPLEMENTADOS EN HACHE BASE.**
- **Criterio de salida P1 completo: NO CERRADO TODAVÍA.**
- Bloqueo restante: pilotear la adopción en un proyecto B/C real y conservar evidencia verificable de campo, restore y comunicación status.

No debe maquillarse ese bloqueo como `PASS`, `N/A` o “resuelto por Core”.

## Qué debe demostrar el piloto B/C

El proyecto piloto debe, como mínimo y según su nivel/CUF aplicables:

- clasificar el proyecto A/B/C y completar sus Critical User Flows;
- ejecutar el reporter P1-01 con evidencia real del proyecto;
- producir evidencia HTTP/build/browser aplicable a sus controles;
- producir evidencia de campo cuando corresponda, sin convertir laboratorio en campo;
- ejecutar un restore drill aislado con RPO/RTO y evidencia del entorno real;
- demostrar status de comunicación/delivery cuando el CUF lo requiera;
- completar inventarios/políticas de terceros, cache, privacidad, artifact promotion y budgets solo cuando sean aplicables;
- mantener `NOT EVALUATED` donde todavía falte evidencia.

La elección del proyecto piloto y cualquier cambio sobre su runtime/infraestructura quedan fuera de este cierre documental y requieren trabajar en el repositorio/entorno del proyecto seleccionado.

## Siguiente frontera segura

Antes de declarar “P1 cerrado”, seleccionar explícitamente un proyecto B/C piloto y ejecutar una adopción controlada. P2 puede investigarse o implementarse después por decisión explícita, pero no debe usarse para esconder el criterio de salida P1 pendiente.

## Guardrails

- No modifica `PRODUCTION-READINESS-STANDARD.md` ni `PRODUCTION-READINESS-CHECKLIST.md`.
- No crea controles nuevos ni cambia severidades/aplicabilidad.
- No declara que Hache Base, por sí sola, demuestre producción de un proyecto derivado.
- No convierte fixtures, templates o CI de Hache Base en evidencia de producción.
- No inicia P2 ni migra automáticamente Hache Natación, PROA u otro proyecto.
