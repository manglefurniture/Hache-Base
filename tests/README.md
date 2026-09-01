# Tests

Suite base para proyectos construidos sobre Hache-Base.

## Incluido

- `static/php-syntax.sh`: sintaxis PHP.
- `static/ProductionReadinessDocsTest.php`: paridad 126/126 entre el registro canónico del Standard y la Checklist.
- `audit/`: pruebas del módulo de auditoría.
- `common/`: utilidades reutilizables, incluyendo estados temporales, zona horaria y contrato de estados asíncronos P0-05.
- `fixtures/async-operations/scenarios.json`: escenarios offline para aceptación, confirmación, timeout ambiguo, retry seguro y reconciliación.
- `ui/`: regresiones de tokens, temas, contraste de fallbacks, presets, estados, responsive/container queries, reduced motion, peso y comportamiento JS; incluye compatibilidad del relieve de backend.
- `security/ProductionReadinessCoreTest.php`: contrato de errores HTTP, request/correlation IDs y redacción/log schema mínimo.
- `deployment/HealthCheckTest.sh`: regresiones offline de liveness/readiness/smoke, incluido body/version incorrecto.
- `smoke/http-smoke.sh`: smoke HTTP configurable y separado de liveness/readiness.
- `integration/`: contratos e integraciones reutilizables; incluye validación offline del mailer HTTPS, HMAC de webhooks y cifrado/versionado de credenciales de pago.
- `run.sh`: punto de entrada común.

## Ejecución

```bash
bash tests/run.sh
```

Si se define `SMOKE_BASE_URL`, el runner ejecuta también el smoke HTTP contra el entorno indicado.

## Regla

Los Critical User Flows deben documentarse con `templates/CRITICAL-USER-FLOWS.md` y tener comprobación automatizada o smoke reproducible antes de producción según el nivel aplicable. Las pruebas con escritura no deben contaminar datos históricos reales.

Cada proyecto añade casos específicos de permisos, sedes, pagos y reglas de negocio sobre fixtures/staging.

Las pruebas base de integraciones no hacen llamadas reales a proveedores ni necesitan secretos. Cada proyecto debe añadir smoke/integration tests contra sandbox/staging cuando el proveedor lo permita y una prueba operativa controlada desde el host real antes de producción.

Los patrones UI reutilizables deben probar sus tokens y estados críticos, pero cada proyecto derivado debe añadir regresiones para controles dinámicos, excepciones planas y clases locales que adopte.

## Errores, logs y correlación

El Core prueba offline:

- códigos canónicos 400/401/403/404/409/422/429/500/503;
- `request_id` y `correlation_id` normalizados;
- payloads de error/éxito con `request_id`;
- schema mínimo de logging y redacción de claves sensibles.

Los proyectos siguen siendo responsables de probar sus códigos de dominio, rutas reales y eventos operativos.

## Estados asíncronos P0-05

`tests/common/AsyncOperationStateTest.php` valida el contrato neutral de operaciones asíncronas y los fixtures de `tests/fixtures/async-operations/scenarios.json`.

La regresión demuestra especialmente que:

- `accepted` no es éxito autoritativo;
- `confirmed` sí es éxito autoritativo del contrato base;
- `outcome_unknown` exige seguimiento/reconciliación y no habilita retry ciego;
- `retry_pending` solo representa un retry ya considerado seguro;
- los estados terminales no vuelven silenciosamente a estados activos;
- cada evento de fixture conserva `request_id` y `correlation_id`.

Estos fixtures no escriben DB ni llaman proveedores. Un proyecto que adopte persistencia debe añadir pruebas de schema, idempotencia, concurrencia y reconciliación propias.

## Liveness, readiness y smoke

`tests/deployment/HealthCheckTest.sh` no necesita red: reemplaza `curl` por un fixture controlado y demuestra que readiness falla ante body/version incorrectos.

El smoke real solo se ejecuta cuando se configura `SMOKE_BASE_URL`; debe apuntar a una URL/entorno controlado.

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
