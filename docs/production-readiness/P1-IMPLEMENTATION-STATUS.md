# Production Readiness P1 — estado de implementación

> Estado documental de Hache Base después de completar los ítems P1-01…P1-11 y la matriz explícita de fixtures A/B/C del roadmap. Este documento **no** modifica el Standard, la Checklist ni los criterios de salida del roadmap y no declara Production Ready a ningún proyecto derivado.

## Corte

- Fecha: 2026-09-05
- Base de este paquete: `19a9c578d589ae6a48b4997ddf2c132227bccdc1`
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

## Cierre de los gates de fixtures A/B/C en Hache Base

`LEVEL-A-B-C-FIXTURES.md` y `tests/level-fixtures/fixtures/level-{a,b,c}.json` hacen explícitos los tres escenarios del roadmap y los conectan con una regresión única de matriz.

- **Nivel A:** escenario informativo solo lectura, sin cuentas, persistencia de negocio ni mutaciones remotas.
- **Nivel B:** el formulario público ya existente queda ligado explícitamente a clasificación, CUF y cobertura de la matriz.
- **Nivel C:** escenario sintético de mutación de capacidad crítica con idempotencia, inbox/outbox, duplicados/out-of-order y reconciliación, sin dinero, inventario real ni proveedor real.

La regresión `ProductionReadinessLevelFixturesTest.php` ejecuta el reporter canónico para A/B/C, comprueba que los 126 controles se proyectan sin auto-PASS y verifica que cada nivel está ligado a archivos reales de headers, errores, CUF y budgets que se ejecutan en la suite normal o en el workflow de CI.

Con este paquete quedan cubiertos en Hache Base dos criterios distintos que antes estaban abiertos:

- **P0:** “Un fixture A, B y C demuestra clasificación y checklist.”
- **P1:** “Fixtures A/B/C cubren headers, errores, CUF y budgets.”

Las regresiones compartidas no se presentan como tres implementaciones duplicadas: cada fixture enlaza de forma explícita su clasificación/CUF con esas pruebas reutilizables. Un verde de Base sigue sin ser evidencia de producción de un proyecto real.

## Estado del criterio de salida P1

El roadmap exige tres condiciones para cerrar P1:

1. CI produce un reporte legible y no declara pruebas humanas inexistentes — **CUBIERTO EN HACHE BASE** por P1-01 y sus regresiones.
2. Fixtures A/B/C cubren headers, errores, CUF y budgets — **CUBIERTO EN HACHE BASE** por la matriz explícita A/B/C y las regresiones enlazadas.
3. Al menos un proyecto B/C piloto produce evidencia de campo, restore y comunicación status — **PENDIENTE DE EVIDENCIA DE PROYECTO**.

Por tanto:

- **P0-01…P0-12 + criterio de fixtures P0: CUBIERTOS EN HACHE BASE.**
- **P1-01…P1-11 + criterio de fixtures P1: CUBIERTOS EN HACHE BASE.**
- **Criterio de salida P1 completo: NO CERRADO TODAVÍA.**
- Único bloqueo restante: seleccionar un piloto B/C que tenga un flujo de comunicación aplicable y conservar evidencia verificable de campo, restore y communication status.

Ese bloqueo no debe maquillarse como `PASS`, `N/A` o “resuelto por Core”.

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

La elección del proyecto piloto y cualquier cambio sobre su runtime/infraestructura pertenecen al repositorio/entorno del proyecto seleccionado.

## Siguiente frontera segura

Después de mergear este paquete con CI verde, la siguiente frontera es **un piloto B/C real con flujo de comunicación aplicable**. Ese piloto debe producir evidencia real de campo, restore y communication status antes de declarar cerrado el criterio de salida P1.

P2 puede investigarse o implementarse después por decisión explícita, pero no debe usarse para esconder el criterio P1 de proyecto todavía pendiente.

## Guardrails

- No modifica `PRODUCTION-READINESS-STANDARD.md` ni `PRODUCTION-READINESS-CHECKLIST.md`.
- No crea controles nuevos ni cambia severidades/aplicabilidad.
- No declara que Hache Base, por sí sola, demuestre producción de un proyecto derivado.
- No convierte fixtures, templates o CI de Hache Base en evidencia de producción.
- No inicia P2 ni migra automáticamente Hache Natación, PROA u otro proyecto.
