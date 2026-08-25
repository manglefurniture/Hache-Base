# Módulos de datos

Estos esquemas son **plantillas**, no migraciones que deban aplicarse automáticamente a todos los proyectos.

## `core.sql`

Modelo genérico para servicios recurrentes: organizaciones, sedes, usuarios, clientes, servicios, planes, horarios, inscripciones, pagos y sesiones.

## `recurring-operations.sql`

Extensión opcional para negocios que manejan asistencia, ausencias y sesiones de reposición/reemplazo.

## Selección

Un restaurante, por ejemplo, podría reutilizar organizaciones, sedes, usuarios y clientes pero reemplazar inscripciones/sesiones por mesas, órdenes e inventario. Un SPA podría reutilizar sedes, clientes, servicios, pagos y adaptar horarios a citas.

No copiar tablas que no correspondan al negocio. Antes de convertir una plantilla en migración:

1. definir la matriz de permisos;
2. decidir si el proyecto es multisede;
3. documentar reglas de negocio;
4. ajustar relaciones e índices;
5. añadir controles de integridad por sede;
6. probar sobre staging/clon.
