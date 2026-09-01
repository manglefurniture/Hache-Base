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
- `security/HeadersTest.php`: contrato P0-07 de headers baseline, HSTS opt-in, CSP report-only/enforce y proxy HTTPS confiable.
- `deployment/HealthCheckTest.sh`: regresiones offline de liveness/readiness/smoke, incluido body/version incorrecto.
- `smoke/http-smoke.sh`: smoke HTTP configurable y separado de liveness/readiness.
- `integration/`: contratos e integraciones reutilizables; incluye mailer HTTPS, HMAC de webhooks, cifrado/versionado de credenciales y persistencia P0-06 inbox/outbox/idempotency.
- `run.sh`: punto de entrada común para pruebas que no requieren MariaDB persistente del workflow.

## Ejecución

```bash
bash tests/run.sh
```

Si se define `SMOKE_BASE_URL`, el runner ejecuta también el smoke HTTP contra el entorno indicado.

La regresión `tests/integration/InboxOutboxMariaDbTest.sh` se ejecuta desde CI después de cargar los schemas opcionales en MariaDB.

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

## Security headers P0-07

`tests/security/HeadersTest.php` prueba el helper sin enviar headers reales y demuestra que:

- el baseline no inventa CSP ni activa HSTS sin aprobación del proyecto;
- al activar HSTS, `includeSubDomains` y `preload` siguen apagados por default;
- `preload` exige HSTS, `includeSubDomains` y `max-age` mínimo de un año;
- `max_age=0` puede expresarse para retiro/rollback cuando corresponda;
- CSP puede permanecer `off`, pasar a `report-only` y solo llegar a `enforce` por configuración explícita;
- la composición CSP rechaza directivas/valores inseguros que podrían inyectar headers;
- `X-Forwarded-Proto` de un cliente o de una IP no confiable no convierte HTTP en HTTPS;
- un proxy confiable debe entregar un único valor de esquema; listas multi-hop se rechazan por ambigüedad.

La prueba offline no sustituye evidencia SEC-001/002/003 del entorno real. Cada proyecto debe verificar TLS, headers por ruta, inventario de subdominios y reportes/CUF CSP mediante `templates/SECURITY-HEADERS.md`.

## Estados asíncronos P0-05

`tests/common/AsyncOperationStateTest.php` valida el contrato neutral de operaciones asíncronas y los fixtures de `tests/fixtures/async-operations/scenarios.json`.

La regresión demuestra especialmente que:

- `accepted` no es éxito autoritativo;
- `confirmed` sí es éxito autoritativo del contrato base;
- `outcome_unknown` exige seguimiento/reconciliación y no habilita retry ciego;
- `retry_pending` solo representa un retry ya considerado seguro;
- los estados terminales no vuelven silenciosamente a estados activos;
- cada evento de fixture conserva `request_id` y `correlation_id`.

## Persistencia P0-06

`tests/integration/AsyncPersistenceContractTest.php` comprueba offline que la plantilla SQL conserva las ocho etiquetas de `AsyncOperationState`, las tres restricciones de unicidad y las marcas `dispatch_started_at`/`effect_started_at` necesarias para distinguir fallos ambiguos.

`tests/integration/InboxOutboxMariaDbTest.sh` usa MariaDB real en CI y demuestra:

- el mismo evento inbound se persiste una sola vez;
- dos workers compitiendo solo consiguen un claim;
- una operación con `dispatch_started_at` + `outcome_unknown` no vuelve a la ruta normal de envío;
- un evento con secuencia antigua no degrada una proyección;
- el reprocess seguro conserva fila e `idempotency_key`;
- un claim ligero duplicado no crea un segundo efecto lógico.

Estos tests validan la plantilla de Hache Base, no sustituyen pruebas del worker/proveedor real de un proyecto derivado.

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
