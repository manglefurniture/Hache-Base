# Production Readiness — Hache Base

Paquete normativo y Core mínimo para demostrar cuándo un proyecto derivado puede considerarse preparado para producción.

## Fuente normativa

`PRODUCTION-READINESS-STANDARD.md` v1.1 es la **única fuente normativa**.

Los demás documentos no crean requisitos nuevos:

- `PRODUCTION-READINESS-CHECKLIST.md` — proyección verificable del registro canónico de controles.
- `PRODUCTION-READINESS-AUDIT.md` — fotografía de Hache Base antes de esta primera implementación; conserva valor histórico para explicar los huecos detectados.
- `PRODUCTION-READINESS-ROADMAP.md` — secuencia de implementación P0/P1/P2/P3.
- `P1-IMPLEMENTATION-STATUS.md` — estado documental de P1-01…P1-11 y de los criterios de salida todavía pendientes: fixtures A/C explícitos que cierren los gates P0/P1 y evidencia de un piloto B/C real con campo, restore y comunicación status.
- `PRODUCTION-READINESS-NORMALIZATION-REPORT.md` — evidencia histórica de la normalización 126/126 Standard ↔ Checklist; no sustituye la norma.
- `RESEARCH-SOURCES.md` — fuentes primarias y referencias técnicas.
- `ASYNC-OPERATIONS.md` — contrato reusable implementado en P0-05 para distinguir aceptación, confirmación, ambigüedad, retry y reconciliación.

Si una síntesis contradice el registro canónico de la sección 24 del Standard, **prevalece el Standard**.

## Primera fase implementada

Esta fase se limitó deliberadamente a:

- **P0-01** — paquete documental normalizado enlazado desde README/catálogo.
- **P0-02** — `templates/CRITICAL-USER-FLOWS.md`.
- **P0-03** — contrato Core de errores HTTP comunes, códigos internos estables y `request_id` sin retirar las APIs existentes de `ApiResponse`.
- **P0-04** — `RequestContext` y logging estructurado mínimo con correlación y redacción de secretos.
- **P0-09** — separación conceptual/operativa de liveness, readiness y smoke; readiness puede validar body/version y usa temporales seguros por ejecución.

## Segunda fase incremental implementada — P0-05

P0-05 añade, sin modificar proveedores ni persistencia real:

- `src/common/AsyncOperationState.php` — vocabulario y transiciones base para operaciones asíncronas/externas;
- `docs/production-readiness/ASYNC-OPERATIONS.md` — semántica de `accepted != confirmed`, ambigüedad, retry y reconciliación;
- `templates/ASYNC-OPERATION-LEDGER.md` — plantilla conceptual de operation/event ledger;
- `tests/fixtures/async-operations/scenarios.json` + `tests/common/AsyncOperationStateTest.php` — fixtures offline que ejercitan aceptación, confirmación, timeout ambiguo, retry seguro y reconciliación.

P0-05 no integra el contrato dentro de `ResendMailer`, pagos, n8n ni otros módulos reales.

## Tercera fase incremental implementada — P0-06

P0-06 añade una Extension **opt-in** de persistencia y claims; no la activa globalmente:

- `integrations/async/README.md` — contrato de inbox, outbox, idempotency claim, concurrencia, eventos fuera de orden y reprocess;
- `database/modules/async-inbox-outbox.sql` — schema plantilla para `integration_inbox`, `integration_outbox` e `integration_idempotency_claims`;
- `templates/INBOX-OUTBOX-IDEMPOTENCY.md` — plantilla de adopción por CUF/integración;
- `tests/integration/AsyncPersistenceContractTest.php` — evita drift entre el vocabulario persistido y `AsyncOperationState`;
- `tests/integration/InboxOutboxMariaDbTest.sh` — regresión MariaDB de duplicado, claim concurrente, ambigüedad, out-of-order y reprocess.

P0-06 **no** introduce Redis, broker, queue manager, worker universal, cron global ni integración automática con Resend/pagos/n8n.

## Cuarta fase incremental implementada — P0-07

P0-07 endurece exclusivamente el baseline de headers asociado a **SEC-001 / SEC-002 / SEC-003**:

- baseline defensivo no persistente;
- HSTS opt-in sin `includeSubDomains`/preload por default;
- CSP `off`/`report-only`/`enforce` por configuración explícita;
- detección HTTPS detrás de proxy confiable limitada a IPs exactas;
- `templates/SECURITY-HEADERS.md` y regresiones dedicadas.

P0-07 no activa CSP/HSTS reales en proyectos derivados.

## Quinta fase incremental implementada — P0-08

P0-08 implementa el contrato reusable de **SEC-007** sin adelantar SEC-008/009/010:

- `security/request-security.php` centraliza HTTPS directo/proxy confiable;
- `security/session-security.php` configura cookies seguras, strict mode, idle/absolute timeout, rotación y destrucción;
- `security/auth.php` añade `login()`/`elevate()` como fronteras explícitas de regeneración;
- `templates/SESSION-SECURITY.md` documenta adopción/evidencia;
- regresiones cubren cookies, proxy, fixation, expiración, elevación y logout.

P0-08 no implementa hashing de passwords, recuperación, MFA, no-enumeración, rate limiting de login ni autorización.

## Sexta fase incremental implementada — P0-10

P0-10 endurece el runner de deploy y la evidencia de fallo parcial sin automatizar restore ni rollback inseguro:

- `deployment/deploy.sh` registra fases canónicas en `DEPLOY_RECORD_FILE` fuera del repo;
- un trap de error emite `DEPLOY_RECOVERY_REQUIRED` con fase, exit code, record, runbook y rollback ref disponibles;
- readiness y smoke pueden ejecutarse antes y después de una ventana de observación;
- `REQUIRE_SMOKE=1` y `REQUIRE_OBSERVATION=1` permiten convertir esos contratos en gates explícitos por entorno;
- ausencia de smoke/ventana con defaults compatibles se registra como `NOT_EVALUATED`, nunca como PASS;
- `deployment/rollback.sh` registra únicamente `event=code_rollback` con `recovery_state=pending_verification`; el estado canónico `rolled_back` se registra después mediante `deployment/mark-deploy-recovery.sh` una vez completadas las verificaciones post-rollback del runbook;
- `deployment/mark-deploy-recovery.sh` permite registrar `manual_recovery`/`rolled_back` después de una recuperación explícita;
- `deployment/DEPLOY-FAILURE-RUNBOOK.md` evita reintentos/rollbacks ciegos y separa código de DB/assets/config;
- `templates/DEPLOY-RECOVERY.md` documenta matriz código/DB/assets/config, compatibilidad, punto de no retorno, smoke, ventana, criterios y drill de staging;
- `tests/deployment/DeployRunnerTest.sh` prueba success, fallo parcial, observación, rollback y manual recovery sobre repos Git temporales.

P0-10 no ejecuta restore de DB, canary, blue-green, failover ni recuperación automática. P0-11 permanece separado porque demostrar restaurabilidad requiere objetivos y evidencia propios.

## Séptima fase incremental implementada — P0-11

P0-11 añade primitives y evidencia reusable para **DB-006 / DB-007** sin convertir Hache Base en un sistema de backup administrado:

- `deployment/backup.sh` usa directorios únicos y crea `backup-manifest.env` + `BACKUP_COMPLETE` únicamente después de un dump/checksum exitosos;
- `deployment/backup-freshness-check.sh` ignora backups incompletos, compara edad contra `RPO_SECONDS` y falla ante missing/stale/timestamp futuro; admite un `BACKUP_ALERT_COMMAND` local opcional;
- `deployment/restore-drill.sh` exige target DB aislado, verifica checksums, ejecuta `RESTORE_VERIFY_COMMAND`, mide edad/RPO y duración/RTO, persiste `RESTORE_DRILL_REPORT_FILE` y limpia por default la DB del drill;
- `templates/BACKUP-RESTORE.md` obliga a definir RPO/RTO, retención, alerta, owner y evidencia del último restore drill;
- `tests/deployment/BackupRecoveryTest.sh` cubre freshness fresh/stale/missing, hook de alerta, rechazo de restore sobre la DB fuente, restore aislado y fallo cuando el backup viola RPO.

P0-11 **no** agenda backups por sí solo, no configura storage/cifrado/provider, no restaura producción automáticamente, no hace failover y no permite marcar DB-006/DB-007 sin evidencia real del proyecto. El job de backup y el freshness check deben integrarse con el monitor/alerta del entorno real.

## Octava fase incremental implementada — P0-12

P0-12 cierra el baseline P0 con una política reusable de supply chain, manteniendo separación explícita entre evidencia disponible y evidencia realmente evaluada:

- `security/supply-chain/` versiona política, checker, allowlist de fixtures, configuración de licencias y accepted risk;
- el baseline bloquea secretos de alta confianza y manifests sin lockfile, y mantiene SCA/licencias en adopción controlada;
- Composer y npm validan lockfiles/grafos soportados contra el árbol de `HEAD`, incluidos workspaces npm y `provide`/`replace` de Composer;
- evidencia SCA ausente o no vinculable queda `NOT EVALUATED`, nunca se convierte en PASS;
- accepted risk solo aplica a vulnerabilidades SCA elegibles con owner, aprobación, mitigación y expiración válida;
- `templates/SUPPLY-CHAIN-TRIAGE.md` documenta stacks, findings, SLA, mitigaciones y evidencia por proyecto;
- regresiones offline cubren secretos, lockfiles, SCA, licencias, workspaces y bordes de evidencia reproducible.

P0-12 no implementa SBOM/provenance, pinning por digest ni history scan exhaustivo; esas capacidades permanecen fuera del baseline P0 y se evalúan en niveles posteriores cuando correspondan.

**Estado del roadmap:** P0-01…P0-12 y P1-01…P1-11 están implementados en Hache Base, pero **los criterios de salida P0 y P1 todavía no están cerrados**. El mismo faltante de fixtures explícitos Nivel A y Nivel C deja abierto el gate P0 de “clasificación + Checklist” y el gate P1 de “headers + errores + CUF + budgets”. Después de cerrar ambos con la matriz A/B/C, P1 todavía exige evidencia real de al menos un proyecto B/C piloto **con flujo de comunicación aplicable**, incluyendo campo, restore y communication status. Ver `P1-IMPLEMENTATION-STATUS.md`. La disponibilidad de una primitive en Hache Base no equivale por sí sola a cumplimiento en un proyecto derivado.

## Uso en un proyecto derivado

1. Clasificar el proyecto A/B/C según el Standard.
2. Completar `templates/CRITICAL-USER-FLOWS.md` para sus CUF reales.
3. Evaluar la Checklist solo con evidencia del proyecto/entorno real.
4. Adoptar las primitives Core que apliquen; no copiar Extensions innecesarias.
5. Si existe una operación asíncrona/externa crítica, definir qué evidencia significa `accepted`, `confirmed`, `failed_final` y cuándo un retry es seguro.
6. Si el CUF necesita dedupe persistente, efectos posteriores al commit o reprocesamiento seguro, completar `templates/INBOX-OUTBOX-IDEMPOTENCY.md` antes de adoptar P0-06.
7. Antes de activar HSTS o promover CSP a enforcement, completar `templates/SECURITY-HEADERS.md`.
8. Si hay sesiones, completar `templates/SESSION-SECURITY.md` y probar cookies/login/expiry/logout/proxy reales.
9. Antes de habilitar deploy de producción, completar `templates/DEPLOY-RECOVERY.md`, definir smoke/ventana/criterios y ejecutar un drill de staging.
10. Cuando DB-006/DB-007 apliquen, completar `templates/BACKUP-RESTORE.md`, conectar backup/freshness a monitoreo y ejecutar un restore drill aislado con RPO/RTO medidos.
11. Cuando P0-12 aplique, completar `templates/SUPPLY-CHAIN-TRIAGE.md`, declarar stacks y conservar `NOT EVALUATED` cuando SCA/licencias no tengan evidencia suficiente.
12. Para adoptar P1, completar solo las plantillas/Extensions aplicables (`THIRD-PARTY-INVENTORY.md`, `CACHE-POLICY.md`, `DATA-PRIVACY-INVENTORY.md`, `ARTIFACT-PROMOTION.md`, `PERFORMANCE-BUDGET.md`) y ejecutar los fixtures/reporters con evidencia del proyecto real.
13. Mantener `NOT EVALUATED` mientras no exista evidencia suficiente. `N/A` exige justificación verificable.

## Contratos Core implementados

### Errores y request ID

`security/api-response.php` conserva `json()`, `success()` y `error()` y añade códigos canónicos, `request_id`, headers de correlación y helpers de payload para pruebas.

### Correlación y logs

- `src/common/RequestContext.php` genera o normaliza `request_id`/`correlation_id`.
- `src/common/StructuredLogger.php` emite JSON mínimo con redacción de secretos.

El logger es una primitive, no una plataforma APM.

### Estados asíncronos y reconciliación

`src/common/AsyncOperationState.php` distingue intención local, aceptación externa, resultado ambiguo, retry seguro, reconciliación y resultado autoritativo.

### Inbox/outbox/idempotency Extension

P0-06 conserva Core de estado separado de persistencia/claims opt-in. Si la frontera externa pudo cruzarse y el resultado se perdió, no se permite retry ciego.

### Security headers

P0-07 separa baseline Core no persistente, políticas HSTS/CSP configurables y evidencia Project.

### Sesiones y trusted HTTPS

P0-08 comparte `RequestSecurity` entre headers y sesión para evitar dos interpretaciones de HTTPS. La primitive no demuestra SEC-007 por sí sola.

### Liveness, readiness y smoke

- `deployment/liveness-check.sh` confirma que el proceso/endpoint responde.
- `deployment/health-check.sh` actúa como readiness y puede validar body/version.
- `tests/smoke/http-smoke.sh` comprueba una ruta funcional configurable.

### Deploy/recovery

P0-10 convierte el runner en una secuencia con estados visibles, record persistente, failure trap, smoke/observación configurables y recuperación explícitamente registrada. Un `DEPLOY_OK` no sustituye la evidencia real exigida por DPL-001–DPL-009.

### Backup freshness y restore drill

P0-11 separa tres evidencias: backup **completo**, freshness dentro del RPO y restore aislado verificado dentro del RTO. Los scripts entregan el contrato y la evidencia técnica mínima; el scheduler, storage, cifrado, alertas reales, credenciales y drill operativo pertenecen al proyecto/entorno.

### Supply chain baseline

P0-12 aporta un gate reproducible para secretos/lockfiles y evidencia controlada de SCA/licencias. Un resultado técnico limpio no sustituye la evaluación contextual del proyecto ni autoriza convertir `NOT EVALUATED` en PASS.

## Regla de promoción

Una primitive o Extension disponible en Hache Base no se considera cumplimiento automático de un proyecto derivado. El proyecto debe aportar la evidencia exigida por su nivel/CUF y por la Checklist.
