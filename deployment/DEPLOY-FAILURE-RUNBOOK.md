# Runbook de fallo parcial de despliegue — P0-10

Este runbook se usa cuando `deployment/deploy.sh` termina con `DEPLOY_RECOVERY_REQUIRED` o cuando health/smoke/observación degradan después de cambiar código.

## Principio

Un fallo de deploy no autoriza un rollback ciego. Código, base de datos, assets y configuración pueden tener compatibilidades distintas. Si volver código puede empeorar integridad, detener tráfico o mutaciones y ejecutar recuperación explícita.

## 1. Congelar la situación

1. No reintentar el deploy automáticamente.
2. Conservar el `DEPLOY_RECORD_FILE`, `ROLLBACK_REF`, target y salida del runner.
3. Identificar `failed_phase` y el último `DEPLOY_STATE` exitoso.
4. Si existe riesgo de corrupción, duplicación, exposición de seguridad o escritura incompatible, detener primero las mutaciones/tráfico afectado según la infraestructura del proyecto.

## 2. Clasificar qué cambió

Usar la matriz completada en `templates/DEPLOY-RECOVERY.md`:

- **Código:** commit anterior, commit target y compatibilidad con el esquema/config actual.
- **DB/esquema:** migraciones aplicadas, reversibilidad y punto de no retorno.
- **Assets/cache:** assets publicados, versionado, invalidación y compatibilidad con HTML/API.
- **Config/secrets:** cambios de variables, credenciales, flags o infraestructura que deban revertirse de forma coordinada.

No asumir que `git checkout` revierte DB, assets externos, caches, secretos o configuración.

## 3. Decidir rollback vs recuperación manual

Rollback de código es candidato cuando el target exacto está identificado, health/smoke falla, el código anterior sigue siendo compatible y volverlo reduce riesgo.

Ejecutar solo código con:

```bash
APP_ROOT=/ruta/app bash deployment/rollback.sh <ROLLBACK_REF>
```

La restauración de DB es deliberadamente separada. No restaurar un dump solo porque falló el deploy; primero verificar historial de migraciones, compatibilidad y backup. P0-11 define la evidencia de restore/RPO/RTO y no forma parte de este runbook.

Si rollback no es seguro, registrar **manual_recovery** y seguir el procedimiento específico del proyecto.

## 4. Verificar recuperación

Después del rollback o recuperación manual:

1. ejecutar readiness;
2. ejecutar el smoke del CUF aplicable;
3. comprobar versión/commit efectivo;
4. revisar señales de error/integridad definidas por el proyecto;
5. observar la ventana definida antes de reabrir o cerrar el incidente.

No declarar recuperación solo porque el comando de rollback terminó.

## 5. Evidencia mínima a conservar

- commit target y commit/rollback ref finalmente activo;
- `DEPLOY_RECORD_FILE` y salida de CI/deploy;
- backup asociado cuando aplica;
- migraciones ejecutadas y punto de no retorno;
- health + smoke post-recuperación;
- ventana de observación;
- decisión `rolled_back` o `manual_recovery`, responsable y motivo.

## Límites

P0-10 hace visible el fallo y aporta el procedimiento. No automatiza restore, failover, canary, blue-green ni rollback de base de datos. Esas decisiones requieren evidencia del proyecto y, cuando corresponda, P0-11/P1/P3.
