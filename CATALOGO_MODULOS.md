# Catálogo de módulos — Hache-Base v1.0

Índice funcional para elegir capacidades sin tener que recordar nombres de archivos.

| Módulo | Estado | Qué resuelve | Cuándo usarlo | Referencia |
| --- | --- | --- | --- | --- |
| Arquitectura base | Listo | Separa interfaz, aplicación, dominio, datos e integraciones | Todos los proyectos de aplicación | `docs/ARQUITECTURA.md` |
| Multisede / multiempresa | Listo | Aísla datos y operaciones por organización o sede | Cadenas, sucursales, escuelas, gimnasios, clínicas, restaurantes, spas | `docs/MULTISEDE.md` |
| Roles y permisos | Listo | Define quién puede hacer qué y en qué contexto | Sistemas con más de un tipo de usuario | `docs/ROLES-Y-PERMISOS.md` |
| Reglas de negocio | Listo | Evita reglas dispersas o contradictorias | Sistemas con lógica operativa | `docs/REGLAS-DE-NEGOCIO.md` |
| Estados temporales e integridad entre vistas | Listo | Deriva FUTURE/ACTIVE/ENDED por fechas, fija zona horaria operativa y evita estados contradictorios entre pantallas | Cursos, campañas, promociones, membresías, reservas, eventos y obligaciones temporales | `docs/ESTADOS-TEMPORALES-E-INTEGRIDAD.md` + `src/common/DateRangeState.php` |
| Seguridad web/API | Listo como base | Sesión, autorización, CSRF, Bearer, rate limit, JSON, headers y respuesta API trazable | Paneles, formularios y APIs | `security/README.md` |
| Errores, request/correlation ID y logging mínimo | Core P0 fase 1 | Códigos HTTP comunes estables, `request_id`, correlación entre fronteras y logs JSON con redacción de secretos | APIs, servicios dinámicos, jobs, webhooks e integraciones | `security/api-response.php` + `src/common/RequestContext.php` + `src/common/StructuredLogger.php` |
| Estados asíncronos + operation/event ledger | Core P0-05 + plantilla opt-in | Distingue intención local, aceptación externa, resultado ambiguo, retry seguro, reconciliación y confirmación autoritativa sin imponer persistencia | Correo transaccional, pagos, jobs, webhooks y cualquier proveedor cuyo resultado final no sea inmediato | `docs/production-readiness/ASYNC-OPERATIONS.md` + `src/common/AsyncOperationState.php` + `templates/ASYNC-OPERATION-LEDGER.md` |
| Inbox / Outbox / Idempotency Claim | Extension P0-06 opt-in | Deduplica eventos, serializa claims, conserva idempotency key, bloquea retry ciego y prueba concurrencia/out-of-order/reprocess | CUF con callbacks repetibles, efectos posteriores al commit o integraciones que deban sobrevivir/reprocesar fallos | `integrations/async/README.md` + `database/modules/async-inbox-outbox.sql` + `templates/INBOX-OUTBOX-IDEMPOTENCY.md` |
| Auditoría de mutaciones | Listo | Registra quién cambió qué, cuándo y en qué contexto; preserva evidencia de snapshots históricos | Pagos, inventario, citas, usuarios, configuración, cierres y conciliaciones | `docs/AUDITORIA.md` |
| Review y cierre de PR | Listo como proceso | Separa CI de revisión, clasifica deuda de review y limita fixes al alcance acordado | Repositorios con PR, CI y revisión automática/humana | `docs/REVIEW-Y-CIERRE-DE-PR.md` |
| Design System 2026 | Listo como infraestructura configurable | Core → Theme → Extensions; tokens Foundation → Semantic → Component; presets, temas, responsive, estados, accesibilidad y guardrails | Toda interfaz pública o administrativa | `DESIGN-SYSTEM-2026-FINAL.md` + `docs/design-system/README.md` + `src/ui/` |
| Production Readiness v1.1 | Norma aprobada + Core P0 fase 1 + P0-05 + P0-06 opt-in | Clasifica riesgo A/B/C, define CUF, Definition of Done, evidencia y checklist; implementa errores/correlación/logging/health, estados asíncronos y persistencia idempotente opcional | Todo proyecto que vaya a producción; especialmente B/C | `docs/production-readiness/README.md` + `docs/production-readiness/PRODUCTION-READINESS-STANDARD.md` |
| Critical User Flows | Plantilla lista | Hace explícitos resultado autoritativo, fallos, idempotencia, pruebas, smoke, señales y recovery por flujo | Antes de declarar Production Ready y desde que exista un CUF significativo | `templates/CRITICAL-USER-FLOWS.md` |
| UI de backend con relieve | Listo como patrón opt-in | Unifica bordes, sombras y estados de controles claros/oscuros con borde superior visible, foco accesible y comportamiento móvil | Paneles administrativos que necesiten una jerarquía visual ligera sin alterar lógica ni layout | `docs/UI-BACKEND-RELIEF.md` + `src/ui/backend-relief.css` |
| Migraciones e integridad | Listo | Cambios de esquema pequeños, probables e idempotentes | Proyectos con MariaDB | `database/MIGRATIONS.md` |
| Modelo de servicios | Plantilla lista | Organizaciones, sedes, usuarios, clientes, servicios, planes, horarios, pagos y sesiones | Academias, spas, gimnasios, clínicas y servicios recurrentes | `database/modules/README.md` |
| Operaciones recurrentes | Plantilla opcional | Asistencia, ausencias y sesiones de reemplazo | Negocios que realmente manejen esas reglas | `database/modules/recurring-operations.sql` |
| Teléfonos E.164 | Listo | Normalización internacional y compatibilidad mexicana histórica +521 | CRM, WhatsApp, clientes internacionales | `src/common/PhoneNormalizer.php` |
| Utilidades comunes | Listo | IDs, email, texto, dinero en centavos, estados temporales, estados asíncronos y request context | Formularios, lógica común e integraciones | `src/common/` |
| Correo transaccional HTTPS | Listo como patrón | Desacopla notificaciones de SMTP/proveedor, documenta autenticación de dominio, secretos, errores e idempotencia | Alertas operativas, confirmaciones y sistemas desplegados en cloud/VPS | `integrations/email/README.md` |
| Pagos externos, webhooks y credenciales versionadas | Listo como patrón + plantilla | Firma de webhooks, verificación autoritativa, monto/moneda, reservas, idempotencia, cifrado y rotación de credenciales sin romper pagos históricos | E-commerce, cobros en línea, boletos, cupos, reservas pagadas o cualquier integración con credenciales rotables | `integrations/payments/README.md` + `integrations/payments/CREDENTIAL-VERSIONING.md` |
| n8n | Listo como patrón | API privada, Bearer, Nginx/PHP-FPM y backup consistente para Docker + SQLite | Automatizaciones desacopladas | `integrations/n8n/README.md` |
| SEO técnico 2026 | Listo como módulo | Baseline de producción, reglas CI, robots/sitemap/schema, smoke tests y guardrails humanos | Sitios públicos o híbridos con objetivo de rastreo/indexación | `seo/README.md` |
| SEO local | Incluido en módulo SEO | Reglas para ubicaciones reales, NAP, GBP, LocalBusiness y páginas locales | Restaurantes, spas, clínicas, escuelas y otros negocios físicos | `seo/checklists/SEO-AUDIT-CHECKLIST.md` |
| Pruebas | Listo como base | Sintaxis, unitarias, smoke, integración y regresiones de Production Readiness Core/Extensions | Todos los proyectos con lógica crítica | `tests/README.md` |
| Liveness / readiness / smoke | Core P0 fase 1 | Separa proceso vivo, servicio listo y smoke funcional; readiness valida body/version cuando se configura | Despliegues y proyectos con runtime dinámico | `deployment/liveness-check.sh` + `deployment/health-check.sh` + `tests/smoke/http-smoke.sh` |
| Backup / rollback | Listo como plantilla | Respaldo MariaDB, commit y reversión de código | Sistemas desplegados en servidor | `deployment/BACKUP-ROLLBACK.md` |
| Runner de despliegue | Listo como plantilla | Preflight → backup → commit → migraciones → tests → readiness | VPS/producción | `deployment/README.md` |
| Configuración / secretos | Listo | Separa código de credenciales, entorno, egress y zona horaria operativa | Todos los despliegues | `docs/CONFIGURATION.md` |
| Development / staging / production | Listo | Separa prueba de producción | Proyectos con datos/operaciones críticas | `docs/ENVIRONMENTS.md` |
| CI | Listo | PHP, shell, pruebas, MariaDB y regresiones SEO automáticas | Repositorios derivados | `.github/workflows/ci.yml` |
| CD a VPS | Plantilla gated | Despliegue manual aprobado por commit exacto | Solo tras configurar staging, secrets y Environment | `.github/workflows/deploy-template.yml` |
| Bootstrap de proyecto | Listo | Selección de módulos, `SEO_MODE` y perfil inicial | Al arrancar un nuevo proyecto | `docs/START-NEW-PROJECT.md` |

## Cómo pedir reutilización

No hace falta mencionar archivos. Ejemplos:

- "Usa Hache-Base para un restaurante con cuatro sucursales."
- "Aplica multisede, roles, seguridad, auditoría y SEO local de Hache-Base."
- "Este proyecto no necesita multisede; usa seguridad, pagos, auditoría, SEO y despliegue."
- "Usa estados temporales para promociones y membresías y configura la zona horaria del negocio."
- "Necesito correo transaccional por HTTPS y pagos con webhooks idempotentes."
- "Necesito una pasarela donde podamos cambiar credenciales sin romper pagos, devoluciones o webhooks antiguos."
- "Necesito una operación externa donde accepted no signifique confirmado y deba poder reconciliar timeouts/retries."
- "Este webhook puede llegar repetido y fuera de orden; adopta inbox/outbox con idempotency claim."
- "Aplica también el proceso de review y cierre de PR de Hache-Base."
- "Usa el patrón de relieve del backend para botones claros, primarios oscuros y controles planos."
- "Aplica el Design System 2026 con Theme propio, nivel Dimensional y soporte light/dark."
- "Aplica Production Readiness y documenta los Critical User Flows antes de producción."
- "Es una app privada: usa Hache-Base con SEO_MODE=private-app."

Al recibir una petición así, consultar este catálogo, revisar la documentación de los módulos elegidos y adaptar configuración/reglas al negocio.

**Reutilizable no significa copiar a ciegas.** Los esquemas de `database/modules/`, scripts de despliegue, patrones UI y controles SEO/Production Readiness son plantillas o contratos que requieren configuración, evidencia y pruebas del proyecto destino.

## Regla de mantenimiento

Cuando un nuevo proyecto produzca una solución genérica bien probada, extraerla a Hache-Base eliminando nombres, datos y reglas exclusivas del negocio; documentarla, probarla y añadirla a este catálogo.

El módulo SEO requiere además revisión periódica porque motores, herramientas, rich results, Core Web Vitals y políticas cambian. Consultar `seo/REVIEW-STATUS.md` antes de usarlo como baseline de un proyecto nuevo.

Production Readiness también requiere revisión periódica según `docs/production-readiness/PRODUCTION-READINESS-STANDARD.md`; una primitive o Extension disponible no equivale a que un proyecto derivado haya pasado sus controles.
