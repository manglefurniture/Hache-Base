# Deploy + Recovery Matrix — P0-10

Completar por proyecto/entorno antes de considerar cumplidos DPL-004, DPL-005, DPL-006 o DPL-008. Esta plantilla no sustituye el Standard.

## Identificación

- Proyecto:
- Entorno:
- Nivel A/B/C:
- Responsable técnico:
- Responsable de negocio/CUF:
- Commit/artefacto target:
- Commit anterior:
- `ROLLBACK_REF` esperado:
- URL/version de readiness:
- Smoke/CUF post-release:
- Ventana de observación:
- Señales/umbrales durante la ventana:

## Matriz de cambio y recuperación

| Componente | ¿Cambia? | Cambio exacto | Compatibilidad hacia atrás/adelante | Target de rollback/recuperación | Punto de no retorno | Evidencia previa/staging |
| --- | --- | --- | --- | --- | --- | --- |
| Código | | | | | | |
| DB/esquema/datos | | | | | | |
| Assets/cache/CDN | | | | | | |
| Config/secrets/flags | | | | | | |

`N/A` requiere justificación verificable. No asumir que un rollback de código revierte DB, assets externos, caches o configuración.

## Migraciones — cuando aplica

- Estrategia de compatibilidad/expand-contract:
- ¿Código anterior funciona con esquema nuevo?:
- ¿Código nuevo funciona con esquema anterior?:
- Migración destructiva/irreversible:
- Punto exacto después del cual rollback de código deja de ser seguro:
- Procedimiento si se cruza ese punto:

## Fases esperadas del runner

El registro debe poder reconstruir, según aplicabilidad:

- `started`
- `code_changed`
- `migrations_applied` o `status=not_applicable`
- `tests_passed`
- `healthy`
- `failed`
- resultado posterior `rolled_back` o `manual_recovery` cuando exista recuperación

Un `DEPLOY_OK` o una pipeline verde no sustituyen health, smoke y observación del servicio real.

## Smoke post-release

- CUF/ruta:
- Precondición:
- Resultado observable esperado:
- Mutación permitida durante smoke:
- Datos de prueba/cleanup:
- `SMOKE_BASE_URL` o `SMOKE_COMMAND`:
- ¿`REQUIRE_SMOKE=1` en este entorno?:

## Ventana de observación

- `OBSERVATION_SECONDS`:
- ¿`REQUIRE_OBSERVATION=1` en este entorno?:
- Señales a observar:
- Umbral que obliga rollback/recuperación:
- Responsable durante la ventana:

La segunda ejecución de readiness/smoke al final de la ventana es un gate mínimo. Error rate, logs, métricas de negocio o integridad siguen siendo responsabilidad del proyecto cuando su riesgo lo requiera.

## Criterios de rollback/recovery

Marcar criterios concretos:

- [ ] readiness falla después del release.
- [ ] smoke/CUF falla.
- [ ] error rate o señal operativa supera el umbral definido.
- [ ] existe corrupción/incompatibilidad de datos.
- [ ] existe exposición de seguridad.
- [ ] otro criterio específico:

Si rollback de código empeora integridad, detener tráfico/mutaciones y ejecutar recuperación manual; no usar rollback ciego.

## Drill de staging

- Fecha:
- Commit target:
- Fallo inducido:
- Fase registrada como `failed`:
- ¿Runbook permitió localizar target/rollback ref?:
- Recovery usado: `rolled_back` / `manual_recovery`:
- Health post-recovery:
- Smoke post-recovery:
- Ventana observada:
- Evidencia/links:
- Hallazgos/deuda:

## Aprobación de release

- Fecha:
- Commit final desplegado:
- `DEPLOY_RECORD_FILE`:
- CI aprobado:
- Health:
- Smoke:
- Ventana:
- Resultado: PASS / FAIL / NOT EVALUATED
- Evaluador:
