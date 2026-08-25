# Tests

Suite base para proyectos construidos sobre Hache-Base.

## Incluido

- `static/php-syntax.sh`: sintaxis PHP.
- `audit/`: pruebas del módulo de auditoría.
- `common/`: utilidades reutilizables.
- `smoke/http-smoke.sh`: health/smoke HTTP configurable.
- `integration/`: requisitos para pruebas con MariaDB, roles, sedes y APIs.
- `run.sh`: punto de entrada común.

## Ejecución

```bash
bash tests/run.sh
```

Si se define `SMOKE_BASE_URL`, el runner ejecuta también el smoke HTTP.

## Regla

Los flujos críticos deben tener comprobación automatizada antes de producción. Las pruebas con escritura no deben contaminar datos históricos reales. Cada proyecto añade casos específicos de permisos, sedes, pagos y reglas de negocio sobre fixtures/staging.
