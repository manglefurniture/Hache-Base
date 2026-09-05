# Production Readiness P1 — estado de implementación

> Estado documental de Hache Base después de completar los ítems P1-01…P1-11 del roadmap. Este documento **no** modifica el Standard, la Checklist ni los criterios de salida del roadmap y no declara Production Ready a ningún proyecto derivado.

## Corte

- Fecha: 2026-09-05
- `main` verificado: `b9045a1a6c5d4ed86a20c114bd53c8b8f9ba3513`
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

## Deuda todavía abierta del criterio de salida P0

Aunque P0-01…P0-12 están implementados, el roadmap exige además como criterio de salida P0 que **un fixture A, B y C demuestre clasificación y checklist**. Ese gate continúa **PENDIENTE**: hoy existe un fixture nivel-específico B, pero no fixtures explícitos A y C equivalentes.

El trabajo A/C que sigue debe cerrar simultáneamente dos alcances distintos, sin confundirlos:

- **P0:** cada fixture A/B/C debe declarar y justificar su nivel, asociar CUF y demostrar la proyección/evaluación de Checklist/readiness correspondiente sin inventar PASS humanos.
- **P1:** esos fixtures A/B/C deben además cubrir de forma demostrable headers, errores, CUF y budgets según el criterio de salida P1.

Por tanto, completar solo páginas genéricas de HTTP/browser o solo etiquetar un fixture como A/C no cerrará el gate; la clasificación y la evidencia de Checklist forman parte explícita de la aceptación P0.

## Estado del criterio de salida P1

El roadmap exige tres condiciones para cerrar P1:

1. CI produce un reporte legible y no declara pruebas humanas inexistentes — **cubierto en Hache Base** por P1-01 y sus regresiones.
2. Fixtures A/B/C cubren headers, errores, CUF y budgets — **PENDIENTE EN HACHE BASE**. Existe un fixture explícito Nivel B (`tests/form-b` / `FORM-B-FIXTURE.md`) y fixtures genéricos HTTP/browser, pero hoy no existen fixtures explícitos Nivel A y Nivel C que demuestren clasificación, CUF y cobertura de la condición como conjunto.
3. Al menos un proyecto B/C piloto produce evidencia de campo, restore y comunicación status — **PENDIENTE DE EVIDENCIA DE PROYECTO**.

Por tanto:

- **P1-01…P1-11: IMPLEMENTADOS EN HACHE BASE.**
- **Criterio de salida P0 completo: NO CERRADO TODAVÍA por el gate de fixtures A/B/C con clasificación + Checklist.**
- **Criterio de salida P1 completo: NO CERRADO TODAVÍA.**
- Bloqueo Base: completar fixtures explícitos A y C que, junto con B, satisfagan tanto el gate P0 como el gate P1 en sus respectivos alcances.
- Bloqueo Project: seleccionar un piloto B/C que tenga un flujo de comunicación aplicable y conservar evidencia verificable de campo, restore y communication status.

Ninguno de esos bloqueos debe maquillarse como `PASS`, `N/A` o “resuelto por Core”.

## Qué debe demostrar el piloto B/C

El proyecto piloto debe, como mínimo:

- estar clasificado B o C y completar sus Critical User Flows;
- incluir al menos un flujo de comunicación aplicable que permita producir la evidencia de `communication status` exigida por el criterio de salida P1;
- ejecutar el reporter P1-01 con evidencia real del proyecto;
- producir evidencia HTTP/build/browser aplicable a sus controles;
- producir evidencia de campo requerida, sin convertir laboratorio en campo;
- ejecutar un restore drill aislado con RPO/RTO y evidencia del entorno real;
- demostrar status de comunicación/delivery del flujo seleccionado;
- completar inventarios/políticas de terceros, cache, privacidad, artifact promotion y budgets cuando sean aplicables;
- mantener `NOT EVALUATED` donde todavía falte evidencia.

Un proyecto B/C sin flujo de comunicación aplicable puede seguir adoptando Hache Base, pero **no puede ser el piloto usado para cerrar esta condición P1** mientras el roadmap exija explícitamente evidencia de communication status.

La elección del proyecto piloto y cualquier cambio sobre su runtime/infraestructura quedan fuera de este cierre documental y requieren trabajar en el repositorio/entorno del proyecto seleccionado.

## Siguiente frontera segura

Antes de declarar cerrados los criterios pendientes hay dos pasos independientes:

1. completar en Hache Base fixtures explícitos Nivel A y Nivel C que, junto con el fixture B, demuestren **clasificación + Checklist** para P0 y **headers + errores + CUF + budgets** para P1;
2. seleccionar explícitamente un proyecto B/C piloto **con flujo de comunicación aplicable** y ejecutar una adopción controlada que produzca evidencia real de campo, restore y communication status.

P2 puede investigarse o implementarse después por decisión explícita, pero no debe usarse para esconder ninguno de los criterios P0/P1 pendientes.

## Guardrails

- No modifica `PRODUCTION-READINESS-STANDARD.md` ni `PRODUCTION-READINESS-CHECKLIST.md`.
- No crea controles nuevos ni cambia severidades/aplicabilidad.
- No declara que Hache Base, por sí sola, demuestre producción de un proyecto derivado.
- No convierte fixtures, templates o CI de Hache Base en evidencia de producción.
- No inicia P2 ni migra automáticamente Hache Natación, PROA u otro proyecto.
