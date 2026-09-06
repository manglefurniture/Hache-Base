# Production Readiness P2 — estado de implementación

> P2 aumenta madurez operativa y no bloquea por sí solo la mayoría de releases. Este documento sigue `PRODUCTION-READINESS-ROADMAP.md` y no modifica el Standard ni la Checklist.

## Corte

- Inicio autorizado: 2026-09-06.
- Base inicial P2: `948fe6fc0cb7db9f58c20c306d1d091f7531bb15`.
- P0: cerrado en Hache Base.
- P1: cerrado en Hache Base con criterio de salida validado por el piloto real Nivel C Hache Natación.
- P2 se implementa incrementalmente; una primitive/Extension disponible no se activa globalmente ni equivale a evidencia de proyecto.

## Estado

| Ítem | Estado | Alcance en Hache Base |
| --- | --- | --- |
| P2-01 | IMPLEMENTADO / MERGEADO | Extension opt-in y vendor-neutral para logs, métricas y trazas; exporter contract, trace context estricto, minimización, fail-open y plantilla de adopción. PR #40, merge `ca7e243f3661f40accf9d1f762e5897b4419cd80`; follow-up automático de ciclo de vida/contexto cerrado en PR #42, merge `0b57b4873e67bfe95284b63713fb6d92f799a8d0`. |
| P2-02 | IMPLEMENTADO / MERGEADO | Política machine-readable de alertas sobre golden signals/CUF, validator determinista, plantilla de runbooks, control de ruido y regresión offline. PR #41, merge `a3398bf0fc7851beb04ea46214def65ce458f236`. |
| P2-03 | IMPLEMENTADO / MERGEADO | Failure fixtures deterministas y solo de test para timeout/429/5xx/DNS/storage, sin retry implícito ni fault injection en producción; plantilla de adopción y regresión integrada a la suite. PR #43, merge `be35f2ea2a2ea526fee130842a7fc4883f5a0427`. |
| P2-04 | NO INICIADO | Upload Extension segura; requiere caso real y threat model antes de promover runtime reusable. |
| P2-05 | NO INICIADO | Rate limit shared-store; requiere Redis/DB/edge real antes de elegir implementación. |
| P2-06 | IMPLEMENTADO / MERGEADO | Pinning inmutable de Actions/containers, checker sobre workflows de HEAD y generación de SBOM CycloneDX 1.6 + provenance de enlace artifact/commit/CI/materiales, sin afirmar firma ni SLSA. PR #44, merge `42fc0e202f903bd9bd64aecbb7c7c97087983935`. |
| P2-07 | CONTRATO IMPLEMENTADO EN ESTE PAQUETE / PILOTO ACTIVO | `templates/RESTORE-HISTORY.md` define scheduler, RPO/RTO project-owned, historial de runs/attempts, retención, fallos visibles y revisión humana. Hache Natación activó la cadencia real en PR #133, merge `a01b3ae7b45a6149a0b60028f143d44b8a8aa866`; falta observar y revisar la primera ejecución programada antes de declarar historia recurrente cerrada. |

## P2-01 — observabilidad neutral

Se implementó la alternativa **adaptadores neutrales** contemplada por el roadmap, no una plataforma APM obligatoria.

Incluye `TelemetryExporter`, `TraceContext`, `ObservabilityBridge`, plantilla de adopción y regresión offline. No instala SDK/collector/provider, no activa telemetría global y no cambia el estado de controles `OBS-*`.

El follow-up del PR #42 endureció el contrato para runtimes persistentes: `RequestContext` debe ser explícito por record o inyectarse como `boundaryContext` scoped a un único request/job; además `measure()` valida el nombre del span antes de ejecutar callbacks con posibles efectos laterales.

## P2-02 — alertas accionables y runbooks

P2-02 materializa el requisito del roadmap y de `OBS-006` sin imponer umbrales universales ni un proveedor de alertas.

Incluye:

- `templates/ALERTING-RUNBOOKS.md` — contrato de adopción por CUF/integración, golden signals, severidad, routing, control de ruido, runbook mínimo y evidencia;
- `templates/alert-policy.example.json` — política machine-readable con ejemplos ficticios;
- `tools/observability/validate-alert-policy.mjs` — valida estructura y exige por alerta ID/CUF/signal/métrica/condición/threshold/ventana/persistencia/severidad/owner/runbook/acción/data source;
- `tests/observability/AlertPolicyTest.mjs` — regresión offline de casos válidos e inválidos;
- integración del test en `tests/run.sh`.

Signals soportadas por el contrato:

- `latency`, `traffic`, `errors`, `saturation`;
- `cuf_success`, `cuf_failure`, `cuf_pending`.

El validator **no decide** si un threshold es correcto para el negocio, si el canal de routing funciona o si el runbook resuelve un incidente real. Esas decisiones/evidencias pertenecen al proyecto.

## Criterio de terminado P2-02 en Base

P2-02 se considera cubierto como contrato reusable cuando:

1. ninguna alerta puede declararse sin threshold, ventana, owner, acción y runbook;
2. las señales del contrato cubren golden signals y resultado/pendientes por CUF;
3. los thresholds permanecen project-owned y deben justificar baseline/revisión;
4. la plantilla exige prueba positiva, negativa/control de ruido y routing real;
5. el runbook exige confirmación, acciones seguras, correlación, recovery, escalación y criterio de cierre;
6. existe una regresión offline que bloquea políticas incompletas o ambiguas.

La existencia de estas plantillas/tests no marca `OBS-006` ni otro control como PASS en un proyecto derivado.

## P2-03 — failure fixtures

P2-03 implementa la frontera reusable de pruebas de fallo sin introducir chaos tooling ni dependencias de infraestructura.

Incluye:

- `tests/fixtures/failures/FailureFixture.php` — harness determinista y solo de test;
- categorías estables para `timeout`, `http_429`, `http_5xx`, `dns` y `storage`;
- metadata de fase, status HTTP y `Retry-After` cuando aplica;
- scripts de fallo repetible para probar fallo→éxito y límites de intentos sin `sleep`, red, DNS o storage real;
- `tests/resilience/FailureFixtureContractTest.php` — regresión de las cinco familias, metadata, secuencias y entradas inválidas;
- `templates/FAILURE-RESILIENCE.md` — matriz de adopción por CUF/adapter, timeout, retry, idempotencia, reconciliación, observabilidad y evidencia;
- integración del contrato a `tests/run.sh`.

La fixture **describe el fallo, no la decisión de negocio**. No expone `should_retry`, estado final ni política universal: cada proyecto/adaptador debe decidir retry/reconcile/final failure según idempotencia, outcome autoritativo, límites y semántica del proveedor.

## Criterio de terminado P2-03 en Base

P2-03 se considera cubierto como primitive/fixture reusable cuando:

1. existen escenarios reproducibles para las cinco familias exigidas por el roadmap;
2. los fixtures no realizan fault injection en producción ni dependen de servicios externos;
3. `429` conserva `Retry-After` como evidencia, pero no autoriza retry por sí mismo;
4. `5xx`, timeout, DNS y storage no implican automáticamente éxito, retry o estado final;
5. el harness permite secuencias deterministas de fallo y recuperación para que un proyecto pruebe límites e idempotencia;
6. la plantilla exige evidencia real del adapter/CUF antes de declarar resiliencia PASS;
7. la suite de Hache Base ejecuta la regresión de contrato.

La existencia de los fixtures no marca controles `ROB-*` ni un proyecto derivado como PASS.

## P2-06 — SBOM, provenance y pinning inmutable

P2-06 se implementa encima de P0-12 y del artifact manifest ya existente, sin introducir un servicio externo ni una afirmación criptográfica ficticia.

Incluye:

- `.github/workflows/ci.yml` con Actions externas fijadas por commit SHA completo y MariaDB fijada por digest SHA-256;
- `tools/supply-chain/p2-evidence.mjs verify-workflows` — lee workflows del árbol versionado de `HEAD` y bloquea Actions/containers mutables;
- `tools/supply-chain/p2-evidence.mjs generate` — verifica los bytes reales del artifact contra `hache-artifact-manifest/v1`, exige que `source_commit` coincida con `HEAD`, genera `sbom.cdx.json` CycloneDX 1.6 y `provenance.json`;
- SBOM desde `package-lock.json`/`npm-shrinkwrap.json` v2/v3 y `composer.lock` versionados; yarn/pnpm quedan explícitamente como cobertura parcial;
- provenance local `hache-release-provenance/v1` con artifact digest, commit, refs de CI/build/test, materiales inmutables de workflows y hash del SBOM;
- `security/supply-chain/P2-06.md` — contrato de adopción y fronteras de confianza;
- `tests/security/P2SupplyChainEvidenceTest.mjs` — regresión de pinning, generación y rechazo de artifact alterado;
- integración del checker y regresión en CI/suite.

La provenance queda marcada `UNSIGNED_PROVENANCE_LINKAGE_ONLY_NOT_SLSA_ATTESTATION`: Hache Base no afirma firma, identidad de builder ni cumplimiento SLSA sin infraestructura real que lo demuestre.

## Criterio de terminado P2-06 en Base

P2-06 se considera cubierto como primitive reusable cuando:

1. las referencias externas de workflows Nivel C pueden verificarse por commit SHA/digest inmutable;
2. el checker usa `HEAD` versionado y no un working tree potencialmente alterado;
3. el SBOM conserva cobertura explícita y no convierte lockfiles no soportados en evidencia completa;
4. provenance queda ligada a los bytes reales del artifact, su manifest, commit y evidencia CI/test;
5. un artifact alterado o commit distinto impide generar evidencia válida;
6. no se confunde provenance de enlace con attestation firmada/SLSA;
7. la suite bloquea regresiones hacia referencias mutables.

La existencia de este tooling no declara un proyecto derivado Production Ready: cada Nivel C debe conservar SBOM/provenance de su release real y su propia revisión.

## P2-07 — restore drills programados e historia

P2-07 extiende el restore aislado de P0-11/DB-007 con una obligación de **recurrencia demostrable** para proyectos Nivel C. Hache Base no impone un cron, RPO/RTO ni un proveedor de artifacts universales.

Incluye:

- `templates/RESTORE-HISTORY.md` — contrato project-owned para scheduler, RPO/RTO, ventana de baja carga, store/retención, identidad de `run_id`/`run_attempt`, minimización y revisión periódica;
- `tests/static/RestoreHistoryTemplateTest.php` — bloquea defaults de negocio incrustados en Base y exige que fallos/reruns permanezcan distinguibles;
- integración de la regresión en `tests/run.sh`;
- piloto real Hache Natación: PR #133 programa el restore el día 1 de cada mes una hora después del backup diario, reutiliza RPO 24 h/RTO 1 h ya aprobados, conserva la ruta manual explícita y retiene evidencia minimizada por 90 días.

La evidencia bootstrap manual de un restore previo demuestra que el mecanismo funciona, pero **no sustituye** la primera ejecución nacida del scheduler. Por eso el piloto queda activo y P2-07 no se declara históricamente cerrado todavía.

## Criterio de terminado P2-07 en Base

El contrato reusable se considera implementado cuando:

1. la plantilla no inventa cadencia, RPO/RTO ni retención universal;
2. exige scheduler real e identidad distinguible de runs/attempts;
3. exige conservar fallos como fallos y no sobrescribir historia con el último PASS;
4. exige backup real, restore aislado, verificación específica y cleanup;
5. exige retención suficiente para observar recurrencia;
6. exige al menos una ejecución programada real antes de cerrar P2-07 en un proyecto;
7. una revisión humana permanece obligatoria.

La madurez del piloto solo podrá cerrarse después de observar y revisar su primera ejecución programada real.

## Siguiente frontera

P2-04 y P2-05 siguen bloqueados hasta existir un caso real que justifique upload/storage o shared-state rate limiting. P2-07 ya tiene contrato reusable y piloto programado, pero su evidencia recurrente está **en construcción** hasta la primera ejecución real del scheduler. No se debe saltar automáticamente a P3 ni inventar infraestructura para cerrar una casilla.
