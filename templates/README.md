# Templates

Plantillas genéricas para iniciar nuevos proyectos.

Todo archivo de esta carpeta debe:

- usar valores ficticios o placeholders;
- evitar dependencias de un negocio específico;
- documentar qué debe personalizarse;
- no contener secretos ni datos reales.

## Plantillas actuales

- `PROJECT-PROFILE.md`: perfil y clasificación inicial del proyecto.
- `CRITICAL-USER-FLOWS.md`: CUF, estados, pruebas, señales y recovery.
- `ASYNC-OPERATION-LEDGER.md`: operación/event ledger opt-in para estados asíncronos, retry y reconciliación.
- `INBOX-OUTBOX-IDEMPOTENCY.md`: adopción P0-06 de dedupe inbound, outbox, claims, concurrencia, out-of-order y reprocess.
- `PERMISSION-MATRIX.md`: matriz de permisos.
- `PERFORMANCE-BUDGET.md`: presupuesto de performance.
- `staging.env.example`: referencia de configuración de staging.

Las plantillas no son implementaciones universales. Los schemas opcionales de `database/modules/` tampoco se aplican automáticamente: cada proyecto debe adaptarlos a su stack, riesgo y evidencia real.
