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
- `SECURITY-HEADERS.md`: adopción P0-07 de CSP report-only/enforce, HSTS, inventario de subdominios y frontera TLS/proxy.
- `SESSION-SECURITY.md`: adopción P0-08 de cookies, fixation, idle/absolute expiry, logout y trusted proxy para sesión.
- `DEPLOY-RECOVERY.md`: adopción P0-10 con matriz código/DB/assets/config, punto de no retorno, smoke, observación, criterios y drill de recovery.
- `BACKUP-RESTORE.md`: adopción P0-11 con RPO/RTO, freshness/alertas y evidencia de restore aislado.
- `RESTORE-HISTORY.md`: adopción P2-07 para proyectos Nivel C con scheduler real, RPO/RTO project-owned, historial de runs/attempts, retención, fallos visibles y revisión humana de la primera ejecución programada.
- `UPLOAD-ADOPTION.md`: adopción P2-04 con caso real/CUF, MIME/content/limits, storage, scanner policy, threat model, cleanup y pruebas negativas sin límites universales.
- `SUPPLY-CHAIN-TRIAGE.md`: adopción P0-12 con stacks/lockfiles, secret scan, SCA, triage/SLA, mitigaciones SEC-014 y revisión de licencias.
- `THIRD-PARTY-INVENTORY.md`: adopción P1-05/PERF-010 con owner, propósito, datos compartidos, timeout/fallback, coste medido, budget P1-11 cuando aplica y criterio de retiro por tercero.
- `CACHE-POLICY.md`: adopción P1-06/PERF-011 con matriz por HTML/assets/API/privado/errores e invalidación reproducible.
- `DATA-PRIVACY-INVENTORY.md`: adopción P1-09/PRIV-001…003 con inventario de datos, minimización, acceso, retención, derechos y analytics/cookies/trackers sin imponer una regla legal universal.
- `ARTIFACT-PROMOTION.md`: adopción P1-10/DPL-001 para build/test una vez, manifest verificable, promoción por digest+commit y rollback sin reconstruir.
- `OBSERVABILITY-ADOPTION.md`: adopción P2-01 de logs/métricas/trazas con exporter neutral, sampling, retención, coste, atributos y fallback.
- `ALERTING-RUNBOOKS.md`: adopción P2-02 de alertas accionables por golden signals/CUF, owner, threshold, ventana, routing, control de ruido y runbook.
- `alert-policy.example.json`: contrato machine-readable P2-02 para `validate-alert-policy.mjs`; contiene únicamente ejemplos ficticios y thresholds no universales.
- `PERMISSION-MATRIX.md`: matriz de permisos.
- `PERFORMANCE-BUDGET.md`: adopción P1-11/PERF-004 con presupuesto versionado para JS/CSS/imágenes/fuentes/terceros y criterios para CI.
- `performance-budget.example.json`: contrato machine-readable P1-11 para `release-budget.mjs`; debe copiarse y completarse con límites justificados por proyecto.
- `staging.env.example`: referencia de configuración de staging.

Las plantillas no son implementaciones universales. Los schemas opcionales de `database/modules/` tampoco se aplican automáticamente: cada proyecto debe adaptarlos a su stack, riesgo y evidencia real.
