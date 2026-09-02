# Backup y rollback

## Antes de producción

Todo despliegue que cambie código o esquema debe tener una reversión real disponible.

`backup.sh` registra el commit actual, estado del repo y un dump consistente de MariaDB. Si existe `.env`, lo copia únicamente al backup protegido del servidor; nunca debe subir a Git.

P0-10 añade `templates/DEPLOY-RECOVERY.md` para declarar por release qué cambia en código, DB/esquema, assets/cache y config/secrets, junto con compatibilidad, target de rollback y punto de no retorno.

## Verificación

- confirmar `BACKUP_OK`;
- conservar `SHA256SUMS`;
- confirmar que `database.sql` no está vacío cuando DB aplica;
- mantener permisos restrictivos en `BACKUP_ROOT`;
- conservar el `DEPLOY_RECORD_FILE` del release;
- probar rollback/fallo parcial en staging;
- probar restauraciones de forma periódica en un entorno no productivo.

## Rollback

El rollback de código y el de base de datos son decisiones separadas. Volver el código automáticamente después de una migración no reversible puede dejar código y esquema incompatibles.

`rollback.sh <commit-o-rama>` restaura solo el código. Si se proporciona `DEPLOY_RECORD_FILE`, registra `event=code_rollback` con `recovery_state=pending_verification`; ese evento confirma únicamente la reversión de código y **no** cierra la recuperación. Después de ejecutar readiness, smoke, comprobación del commit efectivo y la ventana/señales definidas por el runbook, el operador registra el estado canónico final con `mark-deploy-recovery.sh rolled_back`.

Si la base debe volver atrás, usar un backup verificado y un procedimiento explícito de restauración. P0-10 no automatiza restore; P0-11 define RPO/RTO, restore drill y freshness de backups.

Si rollback no es seguro, seguir `DEPLOY-FAILURE-RUNBOOK.md`, ejecutar la recuperación específica del proyecto y registrar el cierre con `mark-deploy-recovery.sh manual_recovery`.

## Criterios de activación

Como mínimo evaluar rollback/recuperación ante:

- readiness o smoke fallido después del release;
- degradación del CUF/error rate por encima del umbral del proyecto;
- corrupción o incompatibilidad de datos;
- exposición de seguridad;
- incompatibilidad conocida entre código, esquema, assets o configuración.

Si volver código empeora integridad, se detienen tráfico/mutaciones afectadas y se ejecuta recuperación explícita en vez de un rollback ciego.

## Retención

Definir por proyecto según espacio, criticidad y obligaciones. Mantener como mínimo el backup previo a un despliegue hasta completar la ventana de observación y un periodo razonable de estabilidad.

Un backup que nunca se prueba no se considera una estrategia de recuperación completa.
