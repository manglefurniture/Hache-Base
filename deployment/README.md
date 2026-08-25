# Deployment

Hache-Base adopta un despliegue verificable y reversible.

## Scripts

- `preflight.sh`: requisitos, repo limpio y capacidad de backup.
- `backup.sh`: commit + dump MariaDB + snapshot local de entorno protegido.
- `deploy.sh`: commit fijado, rollback ref, backup, migraciones configurables, pruebas y health check.
- `health-check.sh`: comprobación HTTP final.
- `rollback.sh`: reversión de código explícita.
- `BACKUP-ROLLBACK.md`: política y límites de recuperación.

## Flujo

`PREFLIGHT -> ROLLBACK_REF -> BACKUP -> TARGET_COMMIT -> MIGRATIONS -> TESTS -> HEALTH -> DEPLOY_OK`

El runner se detiene ante errores. No ejecuta automáticamente un rollback de base de datos: después de migraciones, una reversión automática podría dejar esquema y código incompatibles.

## Requisitos por proyecto

Configurar en el entorno real `APP_ROOT`, `BACKUP_ROOT`, conexión de base, `HEALTHCHECK_URL`, `TARGET_COMMIT` y, cuando aplique, `MIGRATION_COMMAND`/`TEST_COMMAND`.

Probar el runner primero en staging antes de habilitar CI/CD hacia producción.
