# HACHE BASE — PRODUCTION READINESS AUDIT

**Fecha de auditoría:** 1 de septiembre de 2026  
**Repositorio:** `manglefurniture/Hache-Base`  
**Rama auditada:** `main` mediante lectura autenticada de archivos actuales  
**Cambio de estado relevante:** PR #10, “Design System 2026: Core, Themes y auditoría controlada”, figura fusionado el 31 de agosto de 2026 (`head_sha`/merge `31eac06ffd77842a36a7c7ae30c7b463dd00f6c4`).  
**Alcance:** auditoría conceptual/read-only. No hubo código, configuración, commits ni deploy.

**Normalización documental:** el Standard v1.1 incorpora un registro canónico de 126 controles en su sección 24. Esta auditoría usa esos IDs como referencia; la Checklist es una proyección del registro, no una norma paralela.

---

## 1. Escala de clasificación

- **YA RESUELTO:** existe contrato/código/prueba suficiente para la función propia de Hache Base.
- **PARCIALMENTE RESUELTO:** existe patrón o parte del control, pero falta evidencia, cobertura o comportamiento reusable.
- **NO RESUELTO:** no se encontró baseline suficiente.
- **NO APLICA AL CORE:** solo puede comprobarse en una aplicación/entorno real.
- **DEBE SER EXTENSIÓN:** capacidad especializada y opt-in.
- **DEBE SER RESPONSABILIDAD DEL PROYECTO DERIVADO:** depende de reglas, contenido, proveedor, datos o infraestructura reales.

“Listo como patrón” no equivale a “cumplido en todos los proyectos derivados”.

Los estados de evaluación de un proyecto son `PASS`, `FAIL`, `N/A` y `NOT EVALUATED`. Un N/A exige justificación verificable y NOT EVALUATED nunca constituye cumplimiento.

## 2. Evidencia revisada

- `README.md`, `CATALOGO_MODULOS.md`, `docs/ARQUITECTURA.md`.
- `DESIGN-SYSTEM-2026-FINAL.md`, `docs/design-system/{ARCHITECTURE,INITIAL-AUDIT,FINAL-REPORT}.md`, `src/ui/`, `tests/ui/`.
- `docs/{CHECKLIST-NUEVO-PROYECTO,CONFIGURATION,ENVIRONMENTS,AUDITORIA}.md`.
- `security/{README,auth,rate-limit,api-response,headers}.php`.
- `integrations/email/README.md`, `integrations/payments/README.md`.
- `database/MIGRATIONS.md` y validaciones de schemas descritas en CI.
- `deployment/{README,BACKUP-ROLLBACK,preflight,backup,deploy,health-check,rollback}.*`.
- `tests/README.md`, `.github/workflows/{ci,deploy-template}.yml`.
- Norma SEO existente y sus evidencias de regresión, referenciada sin duplicarla.

## 3. Resumen ejecutivo

### Fortalezas actuales

1. Arquitectura `Core → Theme → Extensions` clara, pequeña y configurable.
2. Design System 2026 con primitives, accesibilidad, responsive, reduced motion, estados y budgets estáticos.
3. Baseline SEO maduro, con fixtures y CI.
4. Seguridad de aplicación ya cubre autorización, CSRF, Bearer, headers básicos, respuestas JSON y un rate limiter simple.
5. Pagos/webhooks contienen reglas sólidas de firma, consulta autoritativa, monto/moneda, idempotencia, concurrencia y credenciales versionadas.
6. Migraciones, backups, rollback de código, staging y deploy por commit exacto están documentados y parcialmente automatizados.
7. Auditoría de mutaciones y protección de evidencia histórica están bien conceptualizadas.

### Huecos estructurales

1. No existe baseline reusable de **logging estructurado, request/correlation IDs, métricas y alertas**.
2. No existe contrato persistente general para estados de operaciones, mensajes y webhooks ni re-proceso/reconciliación reusable.
3. Manejo de errores no define todavía taxonomía completa 400/401/403/404/409/422/429/500/502/503 ni request ID público.
4. Health check solo confirma un status HTTP; no distingue liveness/readiness/smoke ni valida cuerpo/versión.
5. Deploy puede fallar después de cambiar código o migrar y deja recuperación manual; no registra fases durables ni ventana de observación.
6. Backup está bien iniciado, pero RPO/RTO, alertas de backup y restore drill no están operacionalizados.
7. Headers carecen de CSP; HSTS con `includeSubDomains` se aplica genéricamente al detectar HTTPS, sin una opt-in que pruebe todos los subdominios.
8. Sesión base no expresa regeneración al autenticar/cambiar privilegio ni confianza de proxy HTTPS; pertenece al flujo auth real, pero el contrato debe exigirlo.
9. Dependencias/supply chain no tienen política formal, scan, lockfile guardrail o SLA de vulnerabilidades.
10. Privacidad existe como checklist, pero falta inventario reusable de datos, finalidades, retención y terceros.

## 4. Matriz de auditoría

| Área / IDs | Estado | Evidencia actual | Hueco verificable | Prioridad | Ubicación correcta |
| --- | --- | --- | --- | --- | --- |
| Clasificación A/B/C (`GOV-001`) | NO RESUELTO | Checklist por módulos, pero sin nivel de riesgo formal. | Falta declarar nivel y elevar rutas críticas. | P0 | CORE contract + PROJECT RESPONSIBILITY |
| Critical User Flows (`GOV-002`, `GOV-003`) | PARCIALMENTE RESUELTO | `tests/README.md` exige flujos críticos; checklist los menciona. | Falta plantilla/matriz con estados, pruebas, señales y recovery por CUF. | P0 | CORE template + PROJECT |
| PERF-001/002 CWV | PARCIALMENTE RESUELTO | Design System fija LCP/INP/CLS y budget UI; SEO contempla performance. | Hache Base no puede medir campo/lab de un proyecto real. | P1 | CORE policy; PROJECT evidence |
| PERF-004 budgets | YA RESUELTO | `templates/PERFORMANCE-BUDGET.md`; test UI 40/12 KiB. | El límite UI es solo del módulo; cada proyecto debe completar presupuesto real. | P1 | CORE template + PROJECT |
| PERF-005–010 assets/terceros | PARCIALMENTE RESUELTO | Contratos de imágenes, fuentes, lazy/LCP y Extensions. | Sin assets ni waterfall real; falta inventario de terceros con dueño/coste/fallback. | P1 | CORE contract + THEME/EXTENSION/PROJECT |
| PERF-011 caché/compresión | NO RESUELTO | API JSON usa `no-store`; SEO cubre partes públicas. | Falta matriz reusable por HTML/assets/API/privado y test real de headers. | P1 | CORE template + PROJECT infra |
| A11Y Core | YA RESUELTO | `src/ui/core`, tests de focus, reduced motion, forced colors, targets y componentes. | Garantía limitada a primitives/fallbacks. | P1 | CORE |
| A11Y Theme/contenido | NO APLICA AL CORE | La auditoría final reconoce que Theme/markup real requieren validación. | Contraste, headings, idioma, alt, multimedia, lector y reflow reales. | P1 | THEME + PROJECT |
| SEC headers básicos | PARCIALMENTE RESUELTO | `security/headers.php`: nosniff, XFO, Referrer, Permissions, HSTS. | Sin CSP; HSTS includeSubDomains no es opt-in; Permissions-Policy debe adaptarse. | P0 | CORE helper + PROJECT infra |
| SEC CSP | NO RESUELTO | README advierte que depende de recursos reales. | Falta plantilla/report-only y verificación por proyecto. | P0 B/C; P1 A | CORE guidance + PROJECT |
| SEC CSRF/authz/injection | YA RESUELTO COMO BASE | Helpers y arquitectura deny-by-default; pruebas base. | Aplicación real debe validar todas las rutas y usar SQL parametrizado. | P0 por proyecto | CORE + PROJECT |
| SEC session | PARCIALMENTE RESUELTO | Secure/HttpOnly/SameSite y logout. | Sin API de login/regeneración, expiración contractual ni trusted proxy scheme. | P0 B/C | CORE contract + PROJECT auth |
| SEC rate limit | PARCIALMENTE RESUELTO | Limitador por sesión con 429/Retry-After y límites documentados. | No sirve para anónimo/API/multiinstancia; no define rutas/umbrales reales. | P0 B/C | CORE interface; EXTENSION shared store; PROJECT |
| SEC uploads | NO RESUELTO | No se encontró módulo de upload. | Falta patrón; no debe entrar al Core runtime sin caso. | P1 cuando aplica | EXTENSION + PROJECT |
| SEC secrets/config | YA RESUELTO COMO POLÍTICA | `CONFIGURATION.md`, entornos, `.env`, GitHub secrets, mínimo alcance. | Falta scan automático/rotación verificada en cada proyecto. | P0 | CORE CI opportunity + PROJECT |
| SEC dependencies | NO RESUELTO | Sin política formal observable. | Lockfiles, SCA, licencias, abandono y SLA. | P0 B/C | CORE policy/CI + PROJECT |
| ROB state model | PARCIALMENTE RESUELTO | Pagos y email distinguen aceptación/confirmación de forma textual. | Falta contrato común initiated/processing/confirmed/failed/retryable/cancelled/unknown. | P0 | CORE contract |
| ROB timeouts/retries | PARCIALMENTE RESUELTO | Docs de email/config/integraciones exigen timeout, límite y backoff. | No existe primitive/policy completa con jitter/Retry-After y pruebas comunes. | P0 B/C | CORE contract; EXTENSION adapter; PROJECT config |
| ROB idempotencia/reconciliación | YA RESUELTO PARA PAGOS / PARCIAL GENERAL | Módulo pagos es fuerte; tests repiten webhooks/jobs. | Otros proveedores/formularios no heredan storage/claim/reprocess. | P0 | CORE contract + EXTENSIONS |
| Error taxonomy (`ERR-001`–`ERR-004`) | PARCIALMENTE RESUELTO | `ApiResponse`, 401 y 429 helpers; config oculta debug. | Falta mapa completo, request ID y páginas/JSON 404/500 estándar. | P0 | CORE |
| OBS logs estructurados | NO RESUELTO | Auditoría de mutaciones no sustituye logs operativos. | Falta schema/logger, severidad, version/environment y redacción. | P0 | CORE contract/primitive |
| OBS request/correlation ID | PARCIALMENTE RESUELTO | Auditoría acepta `request_id`. | No se genera/propaga en request, response e integraciones. | P0 | CORE |
| OBS health | PARCIALMENTE RESUELTO | `health-check.sh` prueba código HTTP con timeout. | Sin liveness/readiness, cuerpo/versión ni dependencia/CUF smoke. Usa ruta temporal global. | P0 | CORE template + PROJECT endpoint |
| OBS metrics/alerts | NO RESUELTO | Checklist dice “monitoreo mínimo”. | Sin golden signals, CUF metrics, umbral, dueño ni runbook. | P0 C; P1 B | EXTENSION + PROJECT; contract CORE |
| FORM UX | YA RESUELTO COMO BASE | Design System: labels/errores/guard doble submit/estados. | Solo UI; no demuestra validación servidor ni persistencia segura. | P1 | CORE component + PROJECT |
| FORM server/spam/privacy | PARCIALMENTE RESUELTO | Security/checklist cubren CSRF/rate limit/datos mínimos. | Falta baseline spam escalonado y evidencia por formulario. | P1 | CORE guidance; EXTENSION CAPTCHA; PROJECT |
| COM email adapter | PARCIALMENTE RESUELTO | `ResendMailer`, provider message ID, idempotency textual, DNS y entrega real. | Sin persistencia de requested/accepted/delivered/bounce ni webhook/reprocess reusable. | P0 B/C | EXTENSION + CORE state contract |
| COM WhatsApp/SMS | DEBE SER EXTENSIÓN | Arquitectura desacopla integraciones. | No corresponde al Core; sí debe cumplir estados/timing/tracing comunes. | P1 cuando aplica | EXTENSION + PROJECT |
| WH pagos | YA RESUELTO COMO PATRÓN | Firma raw/HMAC, consulta autoritativa, unique/upsert, orden tardío, versión credencial. | Cada proveedor necesita manifest y pruebas reales. | P0 por proyecto C | EXTENSION + PROJECT |
| WH persistencia/reprocess genérico | PARCIALMENTE RESUELTO | Docs describen idempotencia y eventos fuera de orden. | Falta inbox/event ledger genérico y estado failed/retry. | P0 | EXTENSION reusable, contract CORE |
| DB migraciones/integridad | YA RESUELTO COMO BASE | Convención, inmutabilidad, staging, constraints; CI valida schemas/idempotencia. | Queries/índices/transacciones reales son del proyecto. | P0 por proyecto | CORE templates + PROJECT |
| DB backup | PARCIALMENTE RESUELTO | Dump consistente, checksum, env protegido, backup previo a deploy. | Sin cifrado externo, freshness alert, RPO/retención concreta. | P0 B/C | CORE script + PROJECT infra |
| DB restore | PARCIALMENTE RESUELTO | Documento exige restauraciones periódicas. | No hay script/runbook validado ni evidencia/medición RTO/RPO. | P0 C; P1 B | CORE template + PROJECT drill |
| DB timezones | YA RESUELTO | IANA explícita, UTC neutro, pruebas de fronteras. | Configuración real sigue siendo del proyecto. | P1 | CORE + PROJECT |
| DEP CI | YA RESUELTO COMO BASE | PHP/shell/tests/MariaDB/SEO/UI y schema idempotence. | No SCA/secret scan/license/SBOM; Actions por tag mayor, no SHA. | P1/P0 según riesgo | CORE CI template + PROJECT |
| CFG entornos | YA RESUELTO | Development/staging/production separados y promoción definida. | Equivalencia/credenciales reales requieren inspección. | P0 por proyecto | CORE policy + PROJECT |
| PRIV checklist | PARCIALMENTE RESUELTO | Responsable, derechos, retención, aviso, anonimización de copias. | Falta data inventory/processing register y tracker/cookie review. | P1 B/C | CORE template + PROJECT legal/product |
| DPL commit/build | PARCIALMENTE RESUELTO | Deploy manual gated por SHA exacto; CI separado. | Runner hace checkout/fetch en producción, no artefacto inmutable construido por CI. | P1 | CORE template + PROJECT infra |
| DPL fases/fallo parcial (`DPL-004`, `DPL-008`) | PARCIALMENTE RESUELTO | `set -Eeuo pipefail`; preflight, backup, tests, health. | No registro durable de fase, trap/runbook automático ni ventana de observación. | P0 | CORE deploy template |
| Rollback código | YA RESUELTO COMO BASE | Ref predeploy y script explícito, rechaza worktree sucio. | Solo código; cada proyecto debe probar compatibilidad. | P0 por proyecto | CORE template + PROJECT |
| Rollback DB/assets/config | PARCIALMENTE RESUELTO | Docs separan DB y exigen backup. | Sin matriz por release ni procedimiento de assets/config. | P0 B/C | CORE template + PROJECT |
| TEST estrategia | PARCIALMENTE RESUELTO | Base amplia, fixtures, flujos críticos, concurrencia/idempotencia para pagos. | Falta matriz A/B/C y CUF→tests; sin E2E genérico ejecutable. | P0 | CORE policy/template + PROJECT |
| SEO | YA RESUELTO | Módulo amplio, CI fixture y checklist. | Evidencia de dominio/URLs reales sigue siendo del proyecto. | P1 | CORE module + PROJECT |
| Automation | PARCIALMENTE RESUELTO | CI, UI budgets, SEO, schemas, shell/PHP tests. | Faltan headers, secrets, SCA, a11y browser, Lighthouse, links, restore/observability. | P1 | CORE CI + EXTENSIONS |

## 5. Hallazgos P0

### P0-01 — No existe una Definition of Done común por nivel

Sin nivel A/B/C y matriz CUF, un proyecto puede “pasar CI” sin probar el flujo que genera ingresos o guarda datos. Crear contratos/documentos, no runtime pesado.

### P0-02 — Observabilidad operativa insuficiente

La auditoría de mutaciones es valiosa, pero no reemplaza logs de errores, request/correlation IDs, métricas o alertas. Hoy no hay una forma uniforme de reconstruir formulario → proveedor → webhook → resultado.

### P0-03 — Operaciones asíncronas no tienen un contrato transversal

Pagos está muy bien resuelto; email solo documenta parte. Falta un estado común, ledger/event record, retries y reconciliación aplicables también a WhatsApp, formularios/jobs y futuros proveedores.

### P0-04 — Error handling y health son demasiado básicos

`ApiResponse` es un buen inicio, pero no normaliza status/codes/request ID. `health-check.sh` acepta cualquier cuerpo con el código esperado, por lo que puede aprobar una página equivocada o un servicio que no está listo.

### P0-05 — Seguridad HTTP/sesión requiere guardrails de entorno

No hay CSP y `includeSubDomains` no debe emitirse de forma genérica antes de confirmar todos los hosts. La detección de HTTPS y regeneración de sesión deben formar parte de un contrato auth/proxy verificable.

### P0-06 — Recuperación no está demostrada

Existe backup y se recomienda restore, pero Production Ready C exige evidencia reciente de restore, RTO/RPO y alertas por backup fallido. “El dump no está vacío” evita cero bytes; no prueba recuperación.

### P0-07 — Deploy parcialmente fallido

Después de checkout/migraciones, una falla de tests/health deja el host en un estado que requiere intervención. El documento reconoce el riesgo, pero falta un estado por fase y runbook/criterio de recuperación reproducible.

### P0-08 — Supply chain sin baseline formal

CI no ejecuta secret scan, SCA o políticas de lockfile/licencias. Puede ser ligero y adaptable al stack; no requiere introducir un framework.

## 6. Core, Theme, Extensions y proyecto

### Debe entrar al Core

- Norma, niveles A/B/C, Definition of Done y checklist.
- Plantilla de CUF y matriz de evidencia.
- Contrato de estados asíncronos e idempotencia.
- Taxonomía de errores y envelope con request ID.
- Schema/primitive ligero de logging y correlación.
- Contratos de health/liveness/readiness y smoke.
- Guardrails de security headers configurables, CSP report-only y HSTS opt-in seguro.
- Plantillas de restore drill, deploy phases y rollback matrix.
- Política de dependencias/secret scanning, sin acoplarse a un package manager.

### Debe quedarse en Theme

- Paleta, fuentes, assets, contraste real, `font-display`, densidad y movimiento.
- Ningún requisito operativo debe resolverse solo desde Theme.

### Debe ser Extension

- Adaptadores de email/WhatsApp/SMS/pagos.
- Inbox/outbox/cola y almacenamiento compartido de rate limits.
- CAPTCHA/anti-bot avanzado, uploads/storage/antimalware.
- OpenTelemetry/APM, error tracker, RUM y plataforma de alertas.
- Herramientas específicas de proveedor o infraestructura.

### Responsabilidad del proyecto derivado

- Nivel de riesgo, CUF, reglas, amenazas, datos y privacidad legal.
- Configuración/secretos/headers/CSP reales.
- Budgets, CWV, contraste, contenido, SEO y accesibilidad reales.
- Índices, queries, migraciones, RPO/RTO, restore y rollback probados.
- Proveedores, timeouts, retries, alertas, runbooks y smoke de producción.

## 7. Compatibilidad y contradicciones

1. **Design System:** compatible. El nuevo estándar referencia sus requisitos y añade evidencia de release/operación. No debe duplicar sus 31 capítulos.
2. **SEO:** compatible. El nuevo estándar solo exige que el artefacto desplegado mantenga la norma SEO y sus pruebas.
3. **Informe final del Design System:** su encabezado conservado en Library decía “PR borrador; no autorizado para merge”, pero el estado GitHub actual indica que PR #10 fue fusionado el 31 de agosto de 2026. El informe es evidencia histórica y su estado Git quedó desactualizado; no debe usarse como fuente del estado actual.
4. **HSTS:** `security/headers.php` aplica `includeSubDomains` automáticamente bajo HTTPS, mientras la nueva norma exige opt-in tras verificar subdominios. Debe registrarse como conflicto P0 para una fase posterior, no corregirse silenciosamente.
5. **“Listo” en catálogo:** varios módulos están correctamente etiquetados “como patrón/plantilla”. La futura documentación debe evitar que “Listo” se interprete como cumplimiento automático en el proyecto derivado.
6. **Checklist normalizada:** cualquier severidad o nivel mostrado por versiones anteriores de la Checklist queda sustituido por los metadatos del registro canónico del Standard. La comparación exhaustiva y las correcciones se documentan en `PRODUCTION-READINESS-NORMALIZATION-REPORT.md`.

## 8. Conclusión

Hache Base ya es fuerte como arquitectura, seguridad de aplicación inicial, SEO, Design System y patrones de pagos/migración. Su siguiente salto no es agregar features: es convertir operación real, fallos externos y recuperación en evidencia uniforme. La primera implementación debería ser documental y de primitives pequeñas; observabilidad avanzada y proveedores deben mantenerse opt-in.
