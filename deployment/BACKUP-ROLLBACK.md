# Backup y rollback

## Antes de producción

Todo despliegue que cambie código o esquema debe tener una reversión real disponible.

`backup.sh` registra el commit actual, estado del repo y un dump consistente de MariaDB. Si existe `.env`, lo copia únicamente al backup protegido del servidor; nunca debe subir a Git. P0-11 añade un manifest sin secretos y el marcador `BACKUP_COMPLETE`, creado únicamente después de terminar dump y checksums; una carpeta incompleta no cuenta como backup válido.

P0-10 añade `templates/DEPLOY-RECOVERY.md` para declarar por release qué cambia en código, DB/esquema, assets/cache y config/secrets, junto con compatibilidad, target de rollback y punto de no retorno. P0-11 añade `templates/BACKUP-RESTORE.md` para RPO/RTO, freshness, alertas y restore drill aislado.

## Verificación de backup — P0-11

- confirmar `BACKUP_OK`;
- conservar `SHA256SUMS`;
- confirmar que `database.sql` no está vacío cuando DB aplica;
- exigir `backup-manifest.env` + `BACKUP_COMPLETE` para considerar el backup completo;
- mantener permisos restrictivos en `BACKUP_ROOT`;
- conservar el `DEPLOY_RECORD_FILE` del release;
- ejecutar `backup-freshness-check.sh` con el `RPO_SECONDS` real del proyecto;
- integrar exit code no-cero del backup job y del freshness check con el monitor/alerta del proyecto;
- probar restauraciones de forma periódica en un entorno no productivo con `restore-drill.sh`.

`backup-freshness-check.sh` ignora carpetas incompletas y selecciona el backup completo más reciente por `created_at_epoch`. Devuelve fallo si no existe backup válido, si el timestamp es inválido/futuro o si la edad supera RPO. `BACKUP_ALERT_COMMAND` permite un wrapper local opcional, pero la integración con el monitor real sigue siendo responsabilidad del proyecto.

## Restore drill — P0-11

`restore-drill.sh` restaura `database.sql` únicamente en una DB aislada. Requiere `RESTORE_CONFIRM_ISOLATED=1`, rechaza que `RESTORE_DB_NAME` coincida con la DB fuente declarada en el manifest, verifica checksums, ejecuta un `RESTORE_VERIFY_COMMAND` específico del proyecto y genera `RESTORE_DRILL_REPORT_FILE` con edad del backup, RPO, duración medida y RTO.

Por default `RESTORE_CLEANUP=1` elimina la DB de drill al finalizar. El script no restaura producción, no selecciona backups automáticamente y no convierte la disponibilidad de esta primitive en evidencia suficiente de DB-006/DB-007: el proyecto debe aportar un backup periódico vigente, una alerta demostrada y un drill real con objetivos medidos.

## Rollback

El rollback de código y el de base de datos son decisiones separadas. Volver el código automáticamente después de una migración no reversible puede dejar código y esquema incompatibles.

`rollback.sh <commit-o-rama>` restaura solo el código. Si se proporciona `DEPLOY_RECORD_FILE`, registra `event=code_rollback` con `recovery_state=pending_verification`; ese evento confirma únicamente la reversión de código y **no** cierra la recuperación. Después de ejecutar readiness, smoke, comprobación del commit efectivo y la ventana/señales definidas por el runbook, el operador registra el estado canónico final con `mark-deploy-recovery.sh rolled_back`.

Si la base debe volver atrás, usar un backup verificado y un procedimiento explícito de restauración. P0-11 demuestra restaurabilidad mediante un drill aislado; no automatiza restore de producción.

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

Definir por proyecto según RPO, espacio, criticidad y obligaciones. Mantener como mínimo el backup previo a un despliegue hasta completar la ventana de observación y un periodo razonable de estabilidad.

Un backup que nunca se prueba no se considera una estrategia de recuperación completa.
