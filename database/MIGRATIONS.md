# Migraciones

## Objetivo

Mantener cada cambio de esquema pequeño, cronológico, comprobable y trazable. Las migraciones sustituyen cambios manuales de producción.

## Convención

Usar nombres cronológicos o secuenciales estables, por ejemplo:

`20260824_add_payment_integrity.sql`

Una migración no debe editarse después de haber sido aplicada en producción. Un cambio posterior se expresa con una migración nueva.

## Reglas

1. Hacer backup antes de una migración de producción.
2. Probar primero sobre staging o un clon de la base real.
3. Preferir operaciones idempotentes cuando MariaDB lo permita.
4. Incluir validaciones posteriores para cambios de integridad.
5. Abortar ante relaciones ambiguas en vez de adivinar una corrección.
6. Separar reparación de datos y cambios estructurales cuando ayude a revisar el riesgo.
7. No depender de una edición manual posterior para completar la migración.
8. Documentar cualquier operación irreversible.

## Flujo mínimo

`backup -> clonar/staging -> aplicar migraciones -> verificar integridad -> pruebas -> producción -> smoke test`

## Integridad

Claves foráneas, índices únicos, constraints y triggers pueden reforzar reglas críticas. La base de datos es una segunda línea de defensa; no debe contener una versión contradictoria de las reglas de la aplicación.

## Rollback

No toda migración admite un rollback SQL seguro. Para cambios destructivos, la recuperación oficial es el backup verificado. Si se crea una migración inversa, debe probarse con el mismo rigor que la migración original.
