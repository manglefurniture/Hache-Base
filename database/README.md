# Database

Patrones reutilizables de persistencia, migraciones e integridad.

## Contenido

- `MIGRATIONS.md`: reglas y flujo de migraciones.
- `migration-template.sql`: punto de partida para una migración nueva.
- `migrations/`: migraciones propias de módulos Hache-Base, como auditoría.
- `integrity/`: criterios para foreign keys, índices, constraints y triggers.
- `modules/`: esquemas de referencia opcionales para nuevos negocios.

## Reglas

- Migraciones pequeñas y cronológicas.
- Evitar cambios manuales de esquema en producción.
- Probar migraciones sobre staging o un clon antes de producción.
- Incluir validaciones posteriores cuando una migración afecte integridad.
- Usar la base como segunda línea de defensa sin duplicar reglas contradictorias.
- Preparar backup/recuperación para cambios destructivos.

Los archivos de `modules/` son plantillas: seleccionar y adaptar, no aplicar todos automáticamente.
