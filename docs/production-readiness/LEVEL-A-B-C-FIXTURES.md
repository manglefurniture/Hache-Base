# Production Readiness — fixtures explícitos A/B/C

Este paquete cierra el hueco de Hache Base detectado después de P1-11: el roadmap exige fixtures explícitos **A, B y C** y no basta con tener pruebas HTTP/browser genéricas sin una clasificación y un CUF asociados.

Los fixtures viven en `tests/level-fixtures/fixtures/level-a.json`, `level-b.json` y `level-c.json`, y se validan con `tests/static/ProductionReadinessLevelFixturesTest.php`.

## Qué demuestra cada fixture

| Nivel | Escenario sintético | Razón de clasificación | CUF representativo |
| --- | --- | --- | --- |
| A | Sitio informativo público, solo lectura | Sin cuentas, persistencia de negocio ni mutaciones remotas | Leer contenido principal, navegar y observar fallos HTTP seguros |
| B | Formulario público interactivo | Acepta input y ejecuta una mutación remota no financiera | Enviar una solicitud una sola vez con validación, CSRF, rate limit y dedupe de fixture |
| C | Mutación de cupo/capacidad crítica con confirmación externa simulada | Duplicar o perder el efecto puede causar daño material | Claim/idempotencia durable, outbox/inbox, eventos repetidos/fuera de orden y reconciliación |

El escenario C es deliberadamente sintético: no usa dinero, inventario real, datos personales ni tráfico hacia un proveedor. Su propósito es demostrar la **forma del contrato Nivel C** usando las regresiones aisladas que ya existen en Hache Base.

## Relación con el criterio de salida P0

El roadmap exige: **“Un fixture A, B y C demuestra clasificación y checklist.”**

La matriz lo demuestra de esta manera:

1. cada fixture declara explícitamente nivel, rationale y señales que elevan o no elevan el riesgo;
2. cada fixture declara al menos un CUF con precondición, pasos, resultado observable, mutaciones, integraciones, fallos, idempotencia, prueba, smoke/señal y recuperación observable;
3. `tools/production-readiness/report.php` se ejecuta para A, B y C y proyecta los 126 controles canónicos según nivel;
4. la regresión verifica que la proyección sigue siendo `NOT_A_PRODUCTION_READY_DECLARATION` y que controles fuera de nivel/aplicables cambian como exige el Standard;
5. no se crea evidencia humana ficticia ni se convierten controles en PASS por el mero hecho de existir el fixture.

Esto demuestra el contrato de **clasificación + Checklist** dentro de Hache Base, sin afirmar que un proyecto derivado haya reunido evidencia real.

## Relación con el criterio de salida P1

El roadmap también exige: **“Fixtures A/B/C cubren headers, errores, CUF y budgets.”**

Cada fixture enlaza explícitamente esas cuatro superficies con regresiones compartidas y ejecutables:

- **headers:** `tests/http/ProductionReadinessHttpTest.sh` y `tests/security/HeadersTest.php`;
- **errores:** HTTP 4xx/5xx y `tests/security/ProductionReadinessCoreTest.php`;
- **CUF:** A usa el flujo público de lectura; B usa `tests/form-b/ProductionReadinessFormBTest.sh`; C usa estado asíncrono + inbox/outbox/idempotencia MariaDB;
- **budgets:** `tests/browser/budgets.json`, `tests/browser/config-contract.mjs` y `tests/performance/ReleaseBudgetTest.mjs`.

Las **regresiones compartidas** no se cuentan como tres implementaciones distintas. El valor de la matriz es que cada nivel queda ligado de forma explícita a su clasificación, CUF y cobertura ejecutable, evitando que un test genérico sea interpretado por sí solo como fixture A/B/C.

`ProductionReadinessLevelFixturesTest.php` comprueba además que todo archivo de evidencia existe y que las pruebas ejecutables referenciadas están conectadas a `tests/run.sh` o al workflow de CI.

## Qué NO demuestra

Un CI verde de esta matriz:

- **no declara Production Ready** a Hache Base ni a ningún proyecto;
- no convierte `NOT EVALUATED` en PASS;
- no reemplaza revisión humana de accesibilidad, seguridad, privacidad, recovery o negocio;
- no demuestra CDN/proxy/TLS/DB/proveedor de un entorno real;
- no sustituye el piloto B/C real requerido por el criterio de salida P1;
- no convierte el dedupe de sesión del fixture B en idempotencia de producción;
- no convierte la base aislada del fixture C en evidencia de restore, concurrencia o reconciliación de un proyecto real.

## Ejecución

La regresión principal se ejecuta dentro de la suite normal:

```bash
php -d zend.assertions=1 -d assert.exception=1 tests/static/ProductionReadinessLevelFixturesTest.php
```

Las pruebas HTTP, formulario B, browser budgets, release budgets y persistencia asíncrona siguen ejecutándose por sus rutas existentes de CI; la matriz valida que esas rutas no se desconecten silenciosamente.

## Estado después de este paquete

Una vez que este paquete esté verde y mergeado:

- el criterio de salida **P0** de fixtures A/B/C para clasificación + Checklist queda cubierto en Hache Base;
- el criterio de salida **P1** de fixtures A/B/C para headers + errores + CUF + budgets queda cubierto en Hache Base;
- permanece abierto el criterio de salida P1 que exige **al menos un proyecto B/C piloto real con evidencia de campo, restore y communication status**, y ese piloto debe incluir un flujo de comunicación aplicable.

La evidencia del piloto pertenece al repositorio y entorno del proyecto seleccionado; no debe simularse desde Core.
