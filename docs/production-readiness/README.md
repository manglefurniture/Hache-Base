# Production Readiness — Hache Base

Paquete normativo y Core mínimo para demostrar cuándo un proyecto derivado puede considerarse preparado para producción.

## Fuente normativa

`PRODUCTION-READINESS-STANDARD.md` v1.1 es la **única fuente normativa**.

Los demás documentos no crean requisitos nuevos:

- `PRODUCTION-READINESS-CHECKLIST.md` — proyección verificable del registro canónico de controles.
- `PRODUCTION-READINESS-AUDIT.md` — fotografía de Hache Base antes de esta primera implementación; conserva valor histórico para explicar los huecos detectados.
- `PRODUCTION-READINESS-ROADMAP.md` — secuencia de implementación P0/P1/P2/P3.
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

P0-06 **no** introduce Redis, broker, queue manager, worker universal, cron global ni integración automática con Resend/pagos/n8n. El proyecto que adopte la Extension debe crear su migración, worker/scheduler, retención, observabilidad y runbook según su riesgo.

## Cuarta fase incremental implementada — P0-07

P0-07 endurece exclusivamente el baseline de headers asociado a **SEC-001 / SEC-002 / SEC-003**:

- `security/headers.php` conserva `Headers::apply()` y añade `Headers::build()` para probar el contrato sin emitir headers;
- `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` y `Permissions-Policy` forman el baseline no persistente;
- HSTS queda desactivado por defecto hasta que el proyecto demuestre HTTPS estable;
- al habilitar HSTS, `includeSubDomains` y `preload` siguen desactivados salvo opt-in explícito;
- CSP queda `off` por default y puede pasar por `report-only` antes de una promoción explícita a `enforce`;
- el helper CSP rechaza composición insegura de directivas/valores;
- `X-Forwarded-Proto` solo se acepta desde IPs exactas de proxy confiable y con un único valor normalizado `https`/`http`;
- `templates/SECURITY-HEADERS.md` obliga a inventariar recursos CSP, subdominios, topología TLS/proxy, evidencia y rollback;
- `tests/security/HeadersTest.php` cubre defaults, HSTS opt-in, `includeSubDomains`/preload, CSP report-only/enforce, header injection y proxy spoofing/ambigüedad.

P0-07 no activa una CSP o HSTS reales en ningún proyecto derivado.

## Quinta fase incremental implementada — P0-08

P0-08 implementa el contrato reusable de **SEC-007** sin adelantar SEC-008/009/010:

- `security/request-security.php` centraliza la detección de HTTPS directo o detrás de proxy confiable para que headers y cookies usen la misma frontera;
- `security/session-security.php` configura cookies seguras, `session.use_strict_mode`, idle/absolute timeout, rotación de ID y destrucción efectiva;
- `security/auth.php` conserva `startSecureSession()`, `user()`, `requireUser()` y `logout()` compatibles y añade `login()`/`elevate()` como fronteras explícitas de regeneración;
- `login()` regenera el ID antes de adjuntar identidad autenticada;
- `elevate()` exige sesión autenticada, conserva el mismo principal y regenera el ID después de una elevación ya autorizada por el proyecto;
- idle/absolute expiry eliminan auth y rotan a una nueva sesión anónima;
- `SameSite=None` solo se admite cuando HTTPS efectivo permite `Secure`;
- `templates/SESSION-SECURITY.md` documenta cookies, fixation, expiración, logout, proxy y evidencia del proyecto;
- `tests/security/SessionSecurityTest.php` cubre cookies, proxy spoofing/multi-hop, login/elevación, expiración exacta y logout.

Defaults P0-08: idle 1800 s, absolute 43200 s, `SameSite=Lax`, cookie host-only, `path=/`, `HttpOnly=true` y `Secure` según HTTPS efectivo. Son baseline configurable y **no sustituyen la decisión/evidencia del proyecto**.

P0-08 no implementa hashing de passwords, recuperación, MFA, no-enumeración, rate limiting de login ni autorización. Tampoco deriva la IP real del cliente desde headers de proxy.

No se implementan todavía P0-10/P0-11/P0-12 ni P1+.

## Uso en un proyecto derivado

1. Clasificar el proyecto A/B/C según el Standard.
2. Completar `templates/CRITICAL-USER-FLOWS.md` para sus CUF reales.
3. Evaluar la Checklist solo con evidencia del proyecto/entorno real.
4. Adoptar las primitives Core que apliquen; no copiar Extensions innecesarias.
5. Si existe una operación asíncrona/externa crítica, definir qué evidencia significa `accepted`, `confirmed`, `failed_final` y cuándo un retry es seguro.
6. Si el CUF necesita dedupe persistente, efectos posteriores al commit o reprocesamiento seguro, completar `templates/INBOX-OUTBOX-IDEMPOTENCY.md` antes de adoptar el schema P0-06.
7. Antes de activar HSTS o promover CSP a enforcement, completar `templates/SECURITY-HEADERS.md` con inventario de recursos, subdominios, proxy/TLS, reportes y rollback.
8. Si hay sesiones, completar `templates/SESSION-SECURITY.md`, migrar asignaciones directas de `$_SESSION['user']` a `Auth::login()`/`Auth::elevate()` y probar cookies/login/expiry/logout/proxy reales.
9. Mantener `NOT EVALUATED` mientras no exista evidencia suficiente. `N/A` exige justificación verificable.

## Contratos Core implementados

### Errores y request ID

`security/api-response.php` conserva `json()`, `success()` y `error()` y añade códigos canónicos, `request_id`, headers de correlación y helpers de payload para pruebas.

### Correlación y logs

- `src/common/RequestContext.php` genera o normaliza `request_id`/`correlation_id`.
- `src/common/StructuredLogger.php` emite JSON mínimo con redacción de secretos.

El logger es una primitive, no una plataforma APM.

### Estados asíncronos y reconciliación

`src/common/AsyncOperationState.php` distingue intención local, aceptación externa, resultado ambiguo, retry seguro, reconciliación y resultado autoritativo. `accepted` nunca se interpreta automáticamente como éxito final.

### Inbox/outbox/idempotency Extension

P0-06 conserva Core de estado separado de persistencia/claims opt-in. Si la frontera externa pudo cruzarse y el resultado se perdió, no se permite retry ciego.

### Security headers

P0-07 separa baseline Core no persistente, políticas HSTS/CSP configurables y evidencia Project. `Headers::build()` facilita pruebas sin emitir headers.

### Sesiones y trusted HTTPS

P0-08 comparte `RequestSecurity` entre P0-07 y P0-08 para evitar dos interpretaciones de HTTPS. `SessionSecurity` aplica cookie `HttpOnly`, `Secure` sobre HTTPS efectivo, SameSite/scope configurables, strict mode, expiración y rotación. `Auth::login()` y `Auth::elevate()` son las fronteras que evitan reutilizar IDs a través de cambios de confianza.

La primitive no demuestra SEC-007 por sí sola: el proyecto debe probar cookies reales, su proxy, el login, la elevación, el timeout y el logout.

### Liveness, readiness y smoke

- `deployment/liveness-check.sh` confirma que el proceso/endpoint responde con el status esperado.
- `deployment/health-check.sh` actúa como gate de readiness y puede validar body/version.
- `tests/smoke/http-smoke.sh` comprueba una ruta funcional configurable.

## Regla de promoción

Una primitive o Extension disponible en Hache Base no se considera cumplimiento automático de un proyecto derivado. El proyecto debe aportar la evidencia exigida por su nivel/CUF y por la Checklist.
