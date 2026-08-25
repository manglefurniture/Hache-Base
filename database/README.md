# Database

Base para patrones reutilizables de persistencia e integridad.

## Reglas

- Migraciones pequeñas y cronológicas.
- Evitar cambios manuales de esquema en producción.
- Probar migraciones sobre una base de staging o clon antes de producción.
- Incluir validaciones posteriores cuando una migración afecte integridad.
- Usar restricciones de base de datos como segunda línea de defensa, sin duplicar reglas de forma contradictoria con la aplicación.
- Preparar rollback o estrategia de recuperación para cambios destructivos.

Las migraciones concretas se incorporarán a medida que los módulos genéricos de Hache-Base sean definidos.
