# Consolidación de Production Readiness — 2026-09

**Corte factual:** 24 de septiembre de 2026

**Repositorio de cambios:** `manglefurniture/Hache-Base`

**Fuentes de evidencia leídas sin modificar:** `manglefurniture/hache-natacion` en `536fe3789bbf6333844e4b2f781e303d2a4cd458` y `manglefurniture/tienda-natacion` en `5a586c566fdbfe200b8c90e6383133b7e45c754b`.

`PRODUCTION-READINESS-STANDARD.md` v1.1 sigue siendo la fuente normativa. Esta consolidación no cambia controles, no convierte una primitive o un verde de Base en `PASS` de un proyecto derivado y no afirma una revisión humana que no está documentada.

## Estado anterior

- El roadmap todavía se describía como “Propuesta de implementación futura; no ejecutada”, aunque P0, P1 y parte de P2 ya estaban integrados.
- `P2-IMPLEMENTATION-STATUS.md` describía P2-04 como si faltara únicamente la revisión humana; la matriz de la plantilla muestra criterios técnicos aún no evaluados.
- README y catálogo no reflejaban todo P0-11/P0-12, P1 ni el estado acotado de P2.
- Audit y Normalization Report son fotografías de 2026-09-01, pero necesitaban una nota que evitara leer sus hallazgos históricos como estado vivo.

Los estados del roadmap significan avance de Hache Base: **IMPLEMENTED** es un contrato, primitive, Extension, plantilla o test integrado; **PILOT ACTIVE**, **TECHNICALLY VERIFIED** y **HUMAN REVIEW PENDING** nunca equivalen a `PASS` de un proyecto. **NOT CURRENTLY JUSTIFIED** no se presenta como bloqueo técnico ni como trabajo pendiente obligatorio.

## P0

| Ítem | Estado real | Límite factual |
| --- | --- | --- |
| P0-01 | **IMPLEMENTED** | Paquete documental y autoridad normativa enlazados. |
| P0-02 | **IMPLEMENTED** | Plantilla de CUF y fixtures explícitos A/B/C. |
| P0-03 | **IMPLEMENTED** | Error contract, códigos estables y `request_id`. |
| P0-04 | **IMPLEMENTED** | Request/correlation context y logging estructurado mínimo. |
| P0-05 | **IMPLEMENTED** | Contrato asíncrono, ledger template y fixtures; no integra proveedores automáticamente. |
| P0-06 | **IMPLEMENTED** | Inbox/outbox/idempotency opt-in; no worker, broker ni cola global. |
| P0-07 | **IMPLEMENTED** | Headers configurables y transición CSP/HSTS opt-in. |
| P0-08 | **IMPLEMENTED** | Sesión, trusted HTTPS, expiración, rotación y logout. |
| P0-09 | **IMPLEMENTED** | Liveness, readiness y smoke diferenciados. |
| P0-10 | **IMPLEMENTED** | Deploy/recovery por fases, failure record y runbook. |
| P0-11 | **IMPLEMENTED** | Backup completo, freshness RPO y restore drill aislado/RTO reusable. |
| P0-12 | **IMPLEMENTED** | Baseline de secretos, lockfiles, SCA/licencias y riesgo aceptado. |

P0 está implementado como baseline reusable. No declara cumplimiento de producción de un proyecto derivado.

## P1

| Ítem | Estado real | Límite factual |
| --- | --- | --- |
| P1-01 | **IMPLEMENTED** | Reporte CI por nivel sin auto-PASS. |
| P1-02 | **IMPLEMENTED** | Fixture HTTP de headers, cache, status, redirects y CSP. |
| P1-03 | **IMPLEMENTED** | Browser audit, Lighthouse y accesibilidad con budgets. |
| P1-04 | **IMPLEMENTED** | RUM/Web Vitals opt-in y minimizado. |
| P1-05 | **IMPLEMENTED** | Inventario de terceros. |
| P1-06 | **IMPLEMENTED** | Matriz de caché e invalidación. |
| P1-07 | **IMPLEMENTED** | Formulario fixture B con validación, CSRF, rate limit, honeypot y dedupe. |
| P1-08 | **IMPLEMENTED** | Estado de email/webhooks opt-in. |
| P1-09 | **IMPLEMENTED** | Inventario de datos, privacidad y retención. |
| P1-10 | **IMPLEMENTED** | Artifact promotion build/test once. |
| P1-11 | **IMPLEMENTED** | Budgets versionados de release/assets. |

El criterio de salida P1 quedó **cerrado** el 2026-09-06 en el alcance documentado: Base aporta CI y fixtures; Hache Natación, piloto real Nivel C, aportó evidencia humana de Field, Restore y Communication status. Field solo acredita `home` desktop/mobile.

## P2

| Ítem | Estado real | Límite factual |
| --- | --- | --- |
| P2-01 | **IMPLEMENTED** | Adaptadores neutrales opt-in, no APM obligatorio. |
| P2-02 | **IMPLEMENTED** | Contrato de alertas/runbooks, sin thresholds/routing universales. |
| P2-03 | **IMPLEMENTED** | Failure fixtures deterministas solo para tests. |
| P2-04 | **IMPLEMENTED; TECHNICALLY VERIFIED / HUMAN REVIEW PENDING** | La matriz de adopción conserva criterios no cerrados. |
| P2-05 | **NOT STARTED / NOT CURRENTLY JUSTIFIED** | No hay evidencia de necesidad multi-instancia/proceso/edge. |
| P2-06 | **IMPLEMENTED** | Pinning inmutable, SBOM y provenance de enlace; no firma/SLSA declarada. |
| P2-07 | **IMPLEMENTED; PILOT ACTIVE / RECURRING EVIDENCE PENDING** | Primera evidencia programada no antes del 2026-10-01. |

### P2-04 — matriz de adopción contra `templates/UPLOAD-ADOPTION.md`

La matriz se limita al piloto de imágenes de producto de Tienda Natación. No evalúa todos los uploads del proyecto ni otros proyectos.

| Criterio exigido por la plantilla | Estado | Evidencia demostrada o límite exacto |
| --- | --- | --- |
| Caso real y threat model revisados | **PASS DEMONSTRATED** | El caso real es `/admin/producto.php`; `P2-04-UPLOAD-PILOT.md` versiona el threat model y sus controles. El checkout de producción fue verificado sin mutar datos de negocio. |
| Policy concreta versionada y justificada | **PASS DEMONSTRATED** | `ProductImageUploadPolicy` fija MIME JPG/PNG/WebP, 8 MB, seis archivos, dimensiones/píxeles y scanner `disabled`; la regresión del proyecto bloquea drift. |
| Transporte, MIME, contenido y límites con pruebas negativas | **NOT EVALUATED** | La regresión cubre MIME declarado falso, contenido truncado, inflación PNG, WebP inválido, decoders no disponibles, tamaño y cantidad, pero inyecta el callback de transporte. No ejercita el `is_uploaded_file()` nativo ni un multipart real contra `/admin/guardar-producto.php`; el PR #7 registró este límite. |
| Storage real evita traversal/overwrite y su exposición está probada | **NOT EVALUATED** | Traversal, nombre generado y no-overwrite están cubiertos por regresión; una imagen real se sirvió como JPEG por HTTPS. No hay prueba no destructiva de que la ruta pública no ejecutaría un script ya presente; una ruta `.php` inexistente que devuelve 404 no lo acredita. |
| Scanner policy explícita, incluso `disabled` | **PASS DEMONSTRATED** | La policy y la regresión fijan `disabled`; no se inventa infraestructura AV no justificada. |
| Cleanup/compensación storage↔metadata probado | **NOT EVALUATED** | El endpoint contiene rollback y borrado de receipts, y la regresión prueba delete de receipt; no hay evidencia de una prueba end-to-end que fuerce fallo de metadata y verifique compensación. |
| Auth/CSRF/rate-limit/auditoría aplicables cubiertos por el proyecto | **NOT EVALUATED** | El endpoint exige auth y CSRF. No se reunió evidencia equivalente para rate limit/auditoría aplicables ni una justificación verificable de no aplicabilidad. |
| Revisión humana valida el flujo real | **FAIL DEMONSTRATED** | El documento de piloto declara expresamente la revisión humana final pendiente. No existe una aprobación de owner que pueda declararse en su lugar. |

La evidencia permite **TECHNICALLY VERIFIED**, pero no adopción cerrada ni `PASS` de proyecto.

### P2-05 y P2-07

P2-05 no abrió una Extension shared-store. La evidencia describe un rate limiter local de Hache Natación y un VPS único; no demuestra el problema que resolverían Redis, DB compartida, edge rate limiting o coordinación multi-proceso. Por eso es **NOT STARTED / NOT CURRENTLY JUSTIFIED**, no bloqueado por una dependencia necesaria hoy.

P2-07 tiene `Production Backup Daily` y `Production Restore Drill` serializados por `workflow_run`: el restore considera un backup programado exitoso de `main` y del día 1 UTC. El bootstrap manual del 2026-09-05 no sustituye recurrencia. Al corte de esta consolidación, el primer día 1 posterior es **2026-10-01**, así que queda **PILOT ACTIVE / RECURRING EVIDENCE PENDING** sin rediseñar el patrón.

## P3

| Ítem | Estado real | Justificación |
| --- | --- | --- |
| P3-01 | **NOT CURRENTLY JUSTIFIED** | No hay necesidad demostrada de canary/blue-green. |
| P3-02 | **NOT CURRENTLY JUSTIFIED** | No hay SLO/error budget formal sustentado por tráfico/operación actual. |
| P3-03 | **NOT CURRENTLY JUSTIFIED** | No hay perfil de carga/capacidad que justifique programa periódico. |
| P3-04 | **NOT CURRENTLY JUSTIFIED** | No hay exposición/incidente que justifique WAF o bot management avanzado. |
| P3-05 | **NOT CURRENTLY JUSTIFIED** | No hay requisito de negocio/RTO/RPO que justifique multi-region o DR avanzado. |

## Correcciones realizadas

- Nuevo documento de consolidación y matriz P2-04.
- Roadmap convertido en documento vivo con estado de P0/P1/P2/P3, preservando la intención original.
- Estado P2-04 corregido para separar verificación técnica, criterios `NOT EVALUATED` y revisión humana.
- P2-05 y P2-07 expresados con los estados actuales y la fecha de recurrencia.
- Índice, README y catálogo actualizados únicamente para capacidades ya existentes.
- Audit y Normalization Report señalados explícitamente como snapshots históricos.
- `tests/static/ProductionReadinessConsolidationTest.php`, conectado a `tests/run.sh`, impide que el roadmap vuelva a presentarse como no ejecutado y protege los estados consolidados.

## Elementos conscientemente NO implementados

- P2-05 shared-store rate limiting, Redis, DB compartida, edge rate limiting o coordinación multi-instancia.
- Cierre definitivo de P2-07 antes de una ejecución recurrente real serializada.
- P3-01…P3-05.
- Mutaciones o pruebas destructivas en los pilotos, infraestructura, proveedores, secretos o privilegios nuevos.

## Riesgos/deuda restante

- P2-04: frontera multipart nativa, exposición pública, compensación storage↔metadata y cobertura conjunta auth/CSRF/rate-limit/auditoría siguen `NOT EVALUATED`; la revisión humana final está pendiente.
- P2-07: primera evidencia recurrente serializada y su revisión humana, no antes del 2026-10-01.
- P2-05 y P3-01…P3-05 siguen sin justificación demostrada; no se creó infraestructura para simularla.
