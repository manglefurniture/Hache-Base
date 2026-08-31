# Tests

Suite base para proyectos construidos sobre Hache-Base.

## Incluido

- `static/php-syntax.sh`: sintaxis PHP.
- `audit/`: pruebas del módulo de auditoría.
- `common/`: utilidades reutilizables, incluyendo estados temporales y zona horaria.
- `ui/`: regresiones de tokens, temas, contraste de fallbacks, presets, estados, responsive/container queries, reduced motion, peso y comportamiento JS; incluye compatibilidad del relieve de backend.
- `smoke/http-smoke.sh`: health/smoke HTTP configurable.
- `integration/`: contratos e integraciones reutilizables; incluye validación offline del mailer HTTPS, HMAC de webhooks y cifrado/versionado de credenciales de pago.
- `run.sh`: punto de entrada común.

## Ejecución

```bash
bash tests/run.sh
```

Si se define `SMOKE_BASE_URL`, el runner ejecuta también el smoke HTTP.

## Regla

Los flujos críticos deben tener comprobación automatizada antes de producción. Las pruebas con escritura no deben contaminar datos históricos reales. Cada proyecto añade casos específicos de permisos, sedes, pagos y reglas de negocio sobre fixtures/staging.

Las pruebas base de integraciones no hacen llamadas reales a proveedores ni necesitan secretos. Cada proyecto debe añadir smoke/integration tests contra sandbox/staging cuando el proveedor lo permita y una prueba operativa controlada desde el host real antes de producción.

Los patrones UI reutilizables deben probar sus tokens y estados críticos, pero cada proyecto derivado debe añadir regresiones para controles dinámicos, excepciones planas y clases locales que adopte.

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

Para webhooks y jobs repetibles, probar la misma entrada más de una vez y eventos fuera de orden. Para efectos secundarios, demostrar que una notificación repetida no duplica ni revierte la mutación central.

Cuando las credenciales de pago sean rotables, añadir regresiones de versión histórica: checkout ligado a una versión, retorno con esa versión, webhook posterior a una rotación y transición legacy con token aunque no exista secreto de webhook.
