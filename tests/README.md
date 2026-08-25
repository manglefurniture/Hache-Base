# Tests

Suite base para proyectos construidos sobre Hache-Base.

## Incluido

- `static/php-syntax.sh`: sintaxis PHP.
- `audit/`: pruebas del módulo de auditoría.
- `common/`: utilidades reutilizables, incluyendo estados temporales y zona horaria.
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

## Reglas temporales

Toda regla cuyo resultado cambie por fecha debe probar, como mínimo:

- día anterior al inicio;
- día exacto del inicio;
- día exacto del final;
- día posterior al final;
- zona horaria operativa correcta.

No es suficiente probar un caso intermedio de `ACTIVO`.

## Consistencia e idempotencia

Cuando varias superficies muestran el mismo estado de negocio, incluir una regresión que demuestre que parten de la misma definición canónica. Si existe una reconciliación persistida, probar que puede ejecutarse repetidamente sin producir resultados contradictorios ni escrituras fuera de su contexto autorizado.

Para obligaciones financieras o equivalentes, probar el recurso exacto: una operación válida sobre otro recurso no debe satisfacer ni bloquear accidentalmente la obligación actual.
