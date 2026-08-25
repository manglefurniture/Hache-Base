# Backup y rollback

## Antes de producción

Todo despliegue que cambie código o esquema debe tener una reversión real disponible.

`backup.sh` registra el commit actual, estado del repo y un dump consistente de MariaDB. Si existe `.env`, lo copia únicamente al backup protegido del servidor; nunca debe subir a Git.

## Verificación

- confirmar `BACKUP_OK`;
- conservar `SHA256SUMS`;
- confirmar que `database.sql` no está vacío;
- mantener permisos restrictivos en `BACKUP_ROOT`;
- probar restauraciones de forma periódica en un entorno no productivo.

## Rollback

El rollback de código y el de base de datos son decisiones separadas. Volver el código automáticamente después de una migración no reversible puede dejar código y esquema incompatibles.

`rollback.sh <commit-o-rama>` restaura solo el código. Si la base debe volver atrás, usar un backup verificado y un procedimiento explícito de restauración.

## Retención

Definir por proyecto según espacio, criticidad y obligaciones. Mantener como mínimo el backup previo a un despliegue hasta completar un periodo razonable de estabilidad.

Un backup que nunca se prueba no se considera una estrategia de recuperación completa.
