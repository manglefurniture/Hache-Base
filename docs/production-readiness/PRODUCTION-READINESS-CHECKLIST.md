# HACHE BASE — PRODUCTION READINESS CHECKLIST

**Fuente normativa:** `PRODUCTION-READINESS-STANDARD.md`, sección 24.  
**Regla:** esta Checklist representa el registro canónico; no crea requisitos ni modifica severidad o aplicabilidad.

## Identificación

- Proyecto:
- Repositorio:
- Commit/artefacto:
- Entorno/URL:
- Nivel: A / B / C
- Fecha:
- Evaluador:
- Dueño técnico:
- Dueño de negocio:

## Estados permitidos

- **PASS:** evidencia suficiente y vigente.
- **FAIL:** incumplimiento o evidencia de control incompleto.
- **N/A:** no aplica, con justificación verificable.
- **NOT EVALUATED:** sin evidencia suficiente; nunca equivale a PASS.

Un Nivel A sin DB, persistencia, formularios, comunicaciones o webhooks marca los controles de esas capacidades como N/A con justificación. Mantiene deploy, rollback de código/assets, seguridad HTTP, performance, accesibilidad, errores, smoke y SEO público.

## Gobierno, alcance y CUF

| ID | Severidad | Aplica | Verificación | Evidencia requerida | Estado | Evidencia / justificación |
| --- | --- | --- | --- | --- | --- | --- |
| [GOV-001] | BLOCKER | A | Declarar y justificar nivel A/B/C; elevar el módulo/ruta que reúna condiciones de mayor riesgo. | Perfil aprobado con criterios de nivel. | NOT EVALUATED |  |
| [GOV-002] | REQUIRED | A | Inventariar URLs/servicios, datos, secretos, dependencias, integraciones y CUF con dueños. | Inventario versionado y responsables. | NOT EVALUATED |  |
| [GOV-003] | REQUIRED | A | Cada CUF documenta precondición, pasos, resultado, mutaciones, fallos, idempotencia cuando aplica, pruebas, smoke y señales. | Matriz CUF enlazada a tests/telemetría/runbook. | NOT EVALUATED |  |
| [GOV-004] | BLOCKER | A | Usar N/A solo por no aplicabilidad demostrada; NOT EVALUATED nunca equivale a PASS. | Justificación y evidencia por cada N/A; estados de evaluación. | NOT EVALUATED |  |

## Performance

| ID | Severidad | Aplica | Verificación | Evidencia requerida | Estado | Evidencia / justificación |
| --- | --- | --- | --- | --- | --- | --- |
| [PERF-001] | REQUIRED | A, cuando hay datos de campo suficientes | Cumplir LCP ≤2.5 s, INP ≤200 ms y CLS ≤0.1 en p75, móvil y desktop, cuando exista campo suficiente. | CrUX/RUM por plantilla/CUF y ventana documentada. | NOT EVALUATED |  |
| [PERF-002] | REQUIRED | A | Sin campo suficiente, medir build de producción en laboratorio móvil/red/CPU representativos y registrar causas. | Reporte versionado de Lighthouse o equivalente. | NOT EVALUATED |  |
| [PERF-003] | REQUIRED | A | No usar score Lighthouse como sustituto de campo; investigar regresión material contra baseline. | Comparación y resolución/aceptación documentada. | NOT EVALUATED |  |
| [PERF-004] | REQUIRED | A | Definir presupuesto justificado para JS, CSS, imágenes, fuentes y terceros. | Presupuesto aprobado y CI cuando sea estable. | NOT EVALUATED |  |
| [PERF-005] | REQUIRED | A, cuando hay imágenes | Imágenes con dimensiones/aspect ratio, responsive cuando corresponde y formatos modernos cuando aportan beneficio. | Markup, network y comparación de peso/calidad. | NOT EVALUATED |  |
| [PERF-006] | REQUIRED | A, cuando hay recursos diferibles | No diferir el recurso LCP si retrasa su descubrimiento; diferir recursos fuera de viewport cuando sea seguro. | Waterfall y elemento LCP identificado. | NOT EVALUATED |  |
| [PERF-007] | REQUIRED | A, cuando hay preload | Usar preload solo para recursos críticos consumidos pronto y con tipo/CORS correctos. | Network sin preloads ociosos/duplicados. | NOT EVALUATED |  |
| [PERF-008] | REQUIRED | A, cuando hay webfonts | Limitar variantes de fuentes, usar formato/display/fallback adecuados y evitar shifts materiales. | Network, CSS y CLS. | NOT EVALUATED |  |
| [PERF-009] | REQUIRED | A | Reducir/diferir JS/CSS no usado, render-blocking y tareas largas; decoración no bloquea CUF. | Coverage, waterfall y long tasks. | NOT EVALUATED |  |
| [PERF-010] | REQUIRED | A, cuando hay terceros | Cada tercero tiene dueño, propósito, datos, coste, timeout/fallback y criterio de retiro. | Inventario y medición con/sin tercero. | NOT EVALUATED |  |
| [PERF-011] | REQUIRED | A | Configurar compresión y caché explícita por HTML, assets, API y datos privados; probar invalidación. | Headers reales y prueba de invalidación/no-store. | NOT EVALUATED |  |
| [PERF-012] | RECOMMENDED | A | Probar además en dispositivo móvil representativo con red/CPU limitadas. | Perfil y resultados registrados. | NOT EVALUATED |  |

## Accesibilidad

| ID | Severidad | Aplica | Verificación | Evidencia requerida | Estado | Evidencia / justificación |
| --- | --- | --- | --- | --- | --- | --- |
| [A11Y-001] | REQUIRED | A | Definir idioma, título, landmarks, headings y orden DOM lógico. | Inspección de páginas/plantillas reales. | NOT EVALUATED |  |
| [A11Y-002] | REQUIRED A; BLOCKER B/C | A | Operar todas las acciones/CUF por teclado, sin traps y con orden lógico. | Prueba manual de teclado sobre CUF. | NOT EVALUATED |  |
| [A11Y-003] | REQUIRED | A | Foco perceptible y no totalmente oculto por sticky/overlays. | Prueba visual/teclado en viewports reales. | NOT EVALUATED |  |
| [A11Y-004] | REQUIRED A; BLOCKER B/C | A, cuando hay controles/formularios | Controles con nombre accesible, labels visibles y ARIA solo cuando es necesaria y veraz. | Accessibility tree + revisión de markup. | NOT EVALUATED |  |
| [A11Y-005] | REQUIRED | B, cuando hay formularios | Errores identifican campo, causa y corrección; no dependen solo de color. | Pruebas de error con teclado/lector. | NOT EVALUATED |  |
| [A11Y-006] | REQUIRED | A | Contraste WCAG 2.2 AA en cada Theme y estado habilitado. | Medición automática + revisión visual. | NOT EVALUATED |  |
| [A11Y-007] | REQUIRED | A, cuando hay acciones | Targets cumplen WCAG 2.2 AA; objetivo Hache 44×44 cuando sea viable. | Medición CSS/viewport y excepciones justificadas. | NOT EVALUATED |  |
| [A11Y-008] | REQUIRED | A, cuando hay modales | Modales gestionan semántica, nombre, foco, modalidad, Escape y retorno. | Test teclado/lector y estado de fondo. | NOT EVALUATED |  |
| [A11Y-009] | REQUIRED | A, cuando existen | Menús/disclosures/navegación móvil exponen estado y funcionan con teclado/tacto sin hover obligatorio. | Test de interacción en móvil/teclado. | NOT EVALUATED |  |
| [A11Y-010] | REQUIRED | A, cuando hay movimiento | Reduced motion, ausencia de flashes peligrosos e información no dependiente del movimiento. | Preferencia reduce + revisión visual. | NOT EVALUATED |  |
| [A11Y-011] | REQUIRED | A, cuando hay contenido no textual/multimedia | Alternativas de imágenes y captions/transcripción/audiodescripción cuando WCAG/contenido lo exige. | Revisión de contenido y reproducción. | NOT EVALUATED |  |
| [A11Y-012] | REQUIRED | A | Probar zoom/reflow, teclado, contraste, errores y lector de pantalla proporcional a los CUF. | Evidencia manual + reporte automatizado complementario. | NOT EVALUATED |  |

## Seguridad

| ID | Severidad | Aplica | Verificación | Evidencia requerida | Estado | Evidencia / justificación |
| --- | --- | --- | --- | --- | --- | --- |
| [SEC-001] | REQUIRED A; BLOCKER B/C | A | HTTPS; HSTS solo tras estabilidad; `includeSubDomains`/preload solo tras verificar todos los subdominios. | TLS/headers reales e inventario de subdominios. | NOT EVALUATED |  |
| [SEC-002] | REQUIRED | A | Aplicar nosniff, Referrer-Policy, Permissions-Policy y anti-framing apropiados. | Headers por rutas representativas. | NOT EVALUATED |  |
| [SEC-003] | RECOMMENDED A; REQUIRED B/C | A | CSP específica, probada y desplegada de forma segura; documentar excepciones. | Header/report-only, reportes y prueba CUF. | NOT EVALUATED |  |
| [SEC-004] | BLOCKER | B | Validar entrada en servidor por tipo, longitud, rango, formato y negocio. | Tests negativos por endpoint/CUF. | NOT EVALUATED |  |
| [SEC-005] | BLOCKER | B | Codificar/sanitizar salida por contexto y parametrizar SQL/comandos/rutas. | Revisión de sinks + tests de inyección. | NOT EVALUATED |  |
| [SEC-006] | BLOCKER | B, cuando hay auth por cookie/mutaciones | Proteger CSRF en mutaciones autenticadas por cookie; métodos seguros no mutan. | Tests CSRF y verificación de métodos. | NOT EVALUATED |  |
| [SEC-007] | BLOCKER | B, cuando hay sesiones | Cookies/sesiones seguras; regeneración al autenticar/elevar; expiración/logout; proxy confiable. | Tests de cookies, fixation, logout y proxy. | NOT EVALUATED |  |
| [SEC-008] | REQUIRED B; BLOCKER C | B, cuando hay autenticación | Auth/recuperación con rate limit, no enumeración práctica, tokens seguros y password hashing; evaluar MFA. | Tests de abuso/recuperación y configuración. | NOT EVALUATED |  |
| [SEC-009] | BLOCKER | B, cuando hay recursos protegidos | Autorizar en servidor deny-by-default por acción/recurso/contexto. | Matriz y tests horizontales/verticales. | NOT EVALUATED |  |
| [SEC-010] | REQUIRED B; BLOCKER C | B, cuando hay rutas expuestas/sensibles | Rate limit en rutas sensibles/costosas; estado compartido en multiinstancia. | Tests 429/Retry-After y arquitectura de storage. | NOT EVALUATED |  |
| [SEC-011] | REQUIRED B; BLOCKER C | B, cuando hay uploads | Uploads con allowlist, contenido/MIME, límites, nombre/storage seguro, auth y controles extra según riesgo. | Corpus de archivos maliciosos y revisión storage. | NOT EVALUATED |  |
| [SEC-012] | BLOCKER | A | No exponer stack, SQL, tokens, paths, claves ni PII en errores públicos. | Tests de fallos y config de producción. | NOT EVALUATED |  |
| [SEC-013] | BLOCKER | A | Secretos fuera de Git/frontend/logs/artifacts; mínimo privilegio, rotación, revocación y separación por entorno. | Secret scan, inventario y drill de rotación crítico. | NOT EVALUATED |  |
| [SEC-014] | REQUIRED A; BLOCKER B/C | A, cuando hay dependencias | No liberar vulnerabilidad explotable crítica/alta sin fix, mitigación equivalente o aislamiento aprobado. | SCA + triage de alcanzabilidad/exposición. | NOT EVALUATED |  |
| [SEC-015] | REQUIRED | B, cuando existen esos eventos | Registrar eventos de auth, denegación, rate limit, cambios sensibles y manipulación, sin secretos. | Catálogo y muestras de logs/auditoría. | NOT EVALUATED |  |
| [SEC-016] | REQUIRED | C | Threat model ligero para CUF C y auth/uploads/pagos/webhooks/datos sensibles. | Documento revisado con mitigaciones. | NOT EVALUATED |  |

## Robustez y resiliencia

| ID | Severidad | Aplica | Verificación | Evidencia requerida | Estado | Evidencia / justificación |
| --- | --- | --- | --- | --- | --- | --- |
| [ROB-001] | BLOCKER | B, cuando hay operación externa asíncrona con efecto relevante | Modelar `INITIATED`, `PROCESSING`, `CONFIRMED`, `FAILED`, `RETRYABLE`, `CANCELLED` y `UNKNOWN` o equivalentes, con transiciones. | Diagrama/tabla de estados + tests de transición. | NOT EVALUATED |  |
| [ROB-002] | REQUIRED B; BLOCKER C | B, cuando el proveedor confirma en fase posterior | Interpretar `2xx` según contrato; aceptación no equivale a entrega/pago/completado. | Tests ACK vs confirmación y evidencia autoritativa. | NOT EVALUATED |  |
| [ROB-003] | REQUIRED B; BLOCKER C | B, cuando hay llamadas externas | Toda llamada externa tiene timeouts finitos de conexión/operación y cancelación. | Config + tests de timeout. | NOT EVALUATED |  |
| [ROB-004] | REQUIRED B; BLOCKER C | B, cuando existe retry | Retry solo temporal/seguro, limitado, con backoff+jitter y `Retry-After`. | Tests 429/5xx/timeout e idempotencia. | NOT EVALUATED |  |
| [ROB-005] | BLOCKER | C | Operación no idempotente usa clave estable, constraint/claim o reconciliación antes de retry. | Tests repetidos y concurrentes. | NOT EVALUATED |  |
| [ROB-006] | REQUIRED B; BLOCKER C | B, cuando hay efectos secundarios | Fallo de notificación/analytics no revierte mutación central confirmada salvo contrato explícito. | Test de proveedor caído después de commit central. | NOT EVALUATED |  |
| [ROB-007] | REQUIRED | B | Cada CUF define modo degradado, bloqueos y mensaje al usuario. | Runbook y prueba de dependencia caída. | NOT EVALUATED |  |
| [ROB-008] | REQUIRED B; BLOCKER C | B, cuando existen estados pendientes/retryables | Pendientes/unknown/retryable son consultables, reprocesables con seguridad y reconciliables. | Reprocess/reconciliation drill. | NOT EVALUATED |  |
| [ROB-009] | REQUIRED | C, cuando hay procesamiento concurrente/cola | Límites de cola/concurrencia/retry evitan cascadas y retry storms. | Load/failure test proporcional. | NOT EVALUATED |  |
| [ROB-010] | REQUIRED | B | Dependencias críticas tienen dueño, impacto y recuperación/cambio documentado. | Inventario y runbook probado proporcionalmente. | NOT EVALUATED |  |

## Errores y observabilidad

| ID | Severidad | Aplica | Verificación | Evidencia requerida | Estado | Evidencia / justificación |
| --- | --- | --- | --- | --- | --- | --- |
| [ERR-001] | BLOCKER | A | Desactivar debug público y probar un 500 controlado sin filtración. | Request/response de prueba y config. | NOT EVALUATED |  |
| [ERR-002] | REQUIRED | B, cuando hay runtime dinámico | Capturar exceptions en frontera, preservar causa internamente y emitir un evento correlacionado. | Test de excepción + log correlacionado. | NOT EVALUATED |  |
| [ERR-003] | REQUIRED | B, cuando hay API/mutaciones | Usar 409/422 para conflicto/validación y no tratar errores de dominio como 500. | Tests de status y códigos internos. | NOT EVALUATED |  |
| [ERR-004] | REQUIRED | A | 404/500 y errores API son seguros y ofrecen navegación/instrucción útil. | Pruebas de rutas/errores reales. | NOT EVALUATED |  |
| [OBS-001] | REQUIRED A cuando dinámico; BLOCKER B/C | A, cuando hay runtime dinámico | Logs estructurados/parseables con UTC, severity, environment, version, event y request ID. | Muestras y validación de schema. | NOT EVALUATED |  |
| [OBS-002] | REQUIRED | B, cuando hay más de una frontera/proceso | Generar/propagar request/correlation IDs y normalizar IDs externos. | Tests request→job/webhook/proveedor. | NOT EVALUATED |  |
| [OBS-003] | REQUIRED | B, cuando hay logs de aplicación | Severidades consistentes; DEBUG no global en producción. | Config y muestras por severidad. | NOT EVALUATED |  |
| [OBS-004] | REQUIRED | B | Eventos permiten reconstruir CUF e integraciones críticas. | Timeline reconstruido desde evidencia. | NOT EVALUATED |  |
| [OBS-005] | REQUIRED B; BLOCKER C | B, cuando hay servicio dinámico | Distinguir liveness/readiness/smoke sin filtrar secretos. | Endpoints/checks y pruebas de fallo. | NOT EVALUATED |  |
| [OBS-006] | RECOMMENDED B; REQUIRED C | B, cuando hay servicio operado | Medir golden signals y CUF; alertas con umbral, ventana, dueño y runbook. | Dashboard/alert tests/runbook. | NOT EVALUATED |  |
| [OBS-007] | REQUIRED | B, cuando hay logs | Definir acceso/retención/redacción; no loggear secretos ni datos sensibles innecesarios. | Política, muestras y test de redacción. | NOT EVALUATED |  |

## Formularios y comunicaciones

| ID | Severidad | Aplica | Verificación | Evidencia requerida | Estado | Evidencia / justificación |
| --- | --- | --- | --- | --- | --- | --- |
| [FORM-001] | BLOCKER | B, cuando hay formularios con efecto | Validar y autorizar en servidor; validación cliente es UX. | Tests negativos servidor. | NOT EVALUATED |  |
| [FORM-002] | REQUIRED | B, cuando hay formularios | Labels/instrucciones/required/tipos/autocomplete/inputmode/errores/foco accesibles. | Test markup, teclado y lector. | NOT EVALUATED |  |
| [FORM-003] | REQUIRED | B, cuando hay formularios | Estados idle/loading/success/error; doble submit UI y dedupe servidor si el efecto importa. | Tests UI + requests repetidos. | NOT EVALUATED |  |
| [FORM-004] | REQUIRED | B, cuando hay formularios | Conservar datos válidos tras error sin persistir secretos/pagos. | Test de error y revisión storage. | NOT EVALUATED |  |
| [FORM-005] | REQUIRED | B, cuando el formulario muta/está expuesto | CSRF según auth y rate limit proporcional. | Tests CSRF/rate limit. | NOT EVALUATED |  |
| [FORM-006] | REQUIRED | B, cuando hay formulario público | Mitigación spam escalonada; CAPTCHA solo con abuso justificado y evaluación a11y/privacidad. | Evidencia de controles/abuso y revisión humana. | NOT EVALUATED |  |
| [FORM-007] | REQUIRED | B, cuando se recopilan datos | Recopilar solo datos necesarios y explicar finalidad/privacidad. | Inventario por campo y UI/política. | NOT EVALUATED |  |
| [COM-001] | REQUIRED B; BLOCKER C | B, cuando hay comunicación transaccional | Persistir canal, template/version, destinatario normalizado, operation/provider ID, estado, attempts y timestamps. | Registro persistente y consultas. | NOT EVALUATED |  |
| [COM-002] | REQUIRED | B, cuando proveedor ofrece esos eventos | Distinguir requested, accepted/sent, delivered, delayed, bounced/failed y suppressed según proveedor. | State mapping + fixtures/webhooks. | NOT EVALUATED |  |
| [COM-003] | REQUIRED | B, cuando hay comunicación transaccional | Templates versionados, escape correcto, remitente/enlaces correctos y sin body sensible en logs por defecto. | Template/version review y muestras. | NOT EVALUATED |  |
| [COM-004] | REQUIRED | B, cuando hay retry/eventos de entrega | Retry temporal limitado, dedupe/claim y no reintentar hard bounce/suppression ciegamente. | Tests de retry/dedupe/bounce. | NOT EVALUATED |  |
| [COM-005] | REQUIRED | C, cuando la comunicación es parte del CUF | Fallback crítico definido y probado, sin promesas documentales falsas. | Failure drill del canal/fallback. | NOT EVALUATED |  |
| [COM-006] | REQUIRED | B, cuando hay comunicación | Verificar identidad/DNS/remitente y prueba real desde host objetivo; privacidad/consentimiento aplicables. | DNS/provider evidence + prueba controlada. | NOT EVALUATED |  |

## Webhooks y base de datos

| ID | Severidad | Aplica | Verificación | Evidencia requerida | Estado | Evidencia / justificación |
| --- | --- | --- | --- | --- | --- | --- |
| [WH-001] | BLOCKER | B, cuando hay webhooks | HTTPS, método/content-type/tamaño y firma sobre raw body; replay/timestamp cuando exista. | Tests firma/replay/request inválido. | NOT EVALUATED |  |
| [WH-002] | REQUIRED B; BLOCKER C | B, cuando hay webhooks con efecto | Persistir provider/event ID/type/received/signature/payload hash o referencia/estado/attempts. | Ledger/event record y constraints. | NOT EVALUATED |  |
| [WH-003] | BLOCKER | B, cuando hay webhooks | Unique/claim evita duplicados; duplicado procesado responde éxito sin repetir efectos. | Tests duplicados/concurrentes. | NOT EVALUATED |  |
| [WH-004] | REQUIRED B; BLOCKER C | B, cuando eventos pueden llegar fuera de orden | No asumir orden; proteger estados finales y comparar versión/timestamp cuando el contrato lo permite. | Tests de permutaciones/tardíos. | NOT EVALUATED |  |
| [WH-005] | REQUIRED | B, cuando hay webhooks | Responder rápido tras validación/persistencia y desacoplar trabajo lento cuando corresponde. | Test de latencia y durable handoff. | NOT EVALUATED |  |
| [WH-006] | REQUIRED B; BLOCKER C | B, cuando webhook es reintentable/crítico | Reintento y re-proceso son seguros; estado failed/dead-letter equivalente y runbook. | Reprocess drill y evidencia de fallo. | NOT EVALUATED |  |
| [WH-007] | BLOCKER | C, cuando webhook cambia pago/estado crítico | En pagos/estado crítico consultar fuente autoritativa y validar referencia, monto, moneda y contexto. | Fixtures/provider sandbox y mismatch tests. | NOT EVALUATED |  |
| [WH-008] | REQUIRED | B, cuando hay webhooks | Logs usan IDs/hash; payload sensible tiene acceso/retención limitados. | Política, muestra de logs/storage. | NOT EVALUATED |  |
| [DB-001] | BLOCKER | B, cuando hay DB/esquema mutable | Migraciones versionadas/inmutables, probadas fuera de producción y verificadas después. | Historial, staging run y checks. | NOT EVALUATED |  |
| [DB-002] | REQUIRED B; BLOCKER C | B, cuando hay DB | Reforzar integridad crítica con tipos/NOT NULL/UNIQUE/CHECK/FK/transacciones/locks según regla. | Schema review + tests de violación/concurrencia. | NOT EVALUATED |  |
| [DB-003] | REQUIRED | B, cuando hay DB con volumen/consultas relevantes | Justificar índices por consultas/constraints y verificar rutas críticas. | EXPLAIN/medición y schema. | NOT EVALUATED |  |
| [DB-004] | BLOCKER | C, cuando hay multi-escritura crítica | Multi-escritura crítica es atómica o tiene compensación/reconciliación. | Tests de fallo parcial/transacción. | NOT EVALUATED |  |
| [DB-005] | REQUIRED | B, cuando hay fechas persistidas/reglas temporales | Timestamps inequívocos y zona IANA aplicada en dominio/presentación. | Schema/config y tests de frontera. | NOT EVALUATED |  |
| [DB-006] | BLOCKER | B, cuando hay datos persistentes no reproducibles | Backups automáticos según RPO, protegidos, retenidos y con alerta de fallo. | Jobs, backup freshness, permisos/cifrado/alerta. | NOT EVALUATED |  |
| [DB-007] | REQUIRED B; BLOCKER C | B, cuando aplica DB-006 | Restore probado aisladamente con RTO/RPO medidos y evidencia vigente. | Restore drill y reporte. | NOT EVALUATED |  |
| [DB-008] | REQUIRED | B, cuando hay borrado/retención | Justificar hard/soft delete por integridad, privacidad, auditoría y recuperación. | Política y tests de referencias. | NOT EVALUATED |  |
| [DB-009] | REQUIRED | C, cuando hay snapshots/evidencia crítica | Preservar evidencia financiera/histórica; no reescribir/eliminar silenciosamente. | Audit trail y tests de corrección. | NOT EVALUATED |  |

## Dependencias, configuración y privacidad

| ID | Severidad | Aplica | Verificación | Evidencia requerida | Estado | Evidencia / justificación |
| --- | --- | --- | --- | --- | --- | --- |
| [DEP-001] | REQUIRED | A, cuando hay dependencias/build | Declarar dependencias directas/transitivas, versionar lockfile si existe y lograr build reproducible. | Manifests/lockfile y clean build. | NOT EVALUATED |  |
| [DEP-002] | REQUIRED | A, cuando se añade/retiene dependencia | Minimizar/justificar dependencia por valor, mantenimiento, licencia y superficie. | Registro de decisión/inventario. | NOT EVALUATED |  |
| [DEP-003] | BLOCKER | B, cuando hay dependencias | Ejecutar SCA y triage por severidad, alcanzabilidad, exposición y SLA. | Reporte SCA y decisiones. | NOT EVALUATED |  |
| [DEP-004] | REQUIRED | A, cuando existe el caso | Paquete abandonado/crítico tiene reemplazo, aislamiento o dueño; majors no se actualizan sin pruebas. | Health review y plan. | NOT EVALUATED |  |
| [DEP-005] | REQUIRED | A, cuando hay terceros/licencias | Licencias compatibles y avisos presentes cuando se distribuye. | Scan/revisión de licencias. | NOT EVALUATED |  |
| [DEP-006] | RECOMMENDED | C | Pin/provenance/SBOM cuando el riesgo lo justifica. | SBOM y configuración CI. | NOT EVALUATED |  |
| [CFG-001] | BLOCKER | A, cuando existen varios entornos/runtime | Separar development, test/staging y production en configuración, datos y credenciales. | Matriz y pruebas de aislamiento. | NOT EVALUATED |  |
| [CFG-002] | BLOCKER | A, cuando existe configuración | Externalizar URLs, DB, proveedores, timeouts, flags y secretos; ejemplos solo ficticios. | Config interface + secret scan. | NOT EVALUATED |  |
| [CFG-003] | BLOCKER | A, cuando hay secretos | Secretos fuera de frontend/Git/logs/artifacts/backups sin protección; rotación/revocación en críticos. | Scan, controles de backup y drill. | NOT EVALUATED |  |
| [CFG-004] | REQUIRED | B, cuando hay runtime/configuración mutable | Startup valida config sin imprimir valores; cambios son auditables y reversibles. | Tests de startup y audit/rollback de config. | NOT EVALUATED |  |
| [PRIV-001] | REQUIRED | B, cuando hay datos personales | Inventariar datos personales, finalidad, base, terceros, retención, acceso y canal de derechos según jurisdicción. | Registro y política aprobada. | NOT EVALUATED |  |
| [PRIV-002] | REQUIRED | B, cuando hay datos personales | Minimizar por campo y aplicar controles de acceso/cifrado/eliminación/anonimización según riesgo/ley. | Field inventory, access tests y retention process. | NOT EVALUATED |  |
| [PRIV-003] | REQUIRED | A, cuando existen | Inventariar/configurar analytics, cookies y trackers según consentimiento/ley. | Scan/inventario y comportamiento de consentimiento. | NOT EVALUATED |  |

## Deployment, testing y SEO

| ID | Severidad | Aplica | Verificación | Evidencia requerida | Estado | Evidencia / justificación |
| --- | --- | --- | --- | --- | --- | --- |
| [DPL-001] | BLOCKER | A | Desplegar artefacto/commit exacto aprobado; separar build de release/run. | Provenance/commit y CI aprobado. | NOT EVALUATED |  |
| [DPL-002] | BLOCKER | A | Preflight valida runtime, config, espacio/permisos, backup readiness, conectividad y compatibilidad aplicables. | Salida preflight y revisión por nivel; DB checks N/A en A sin DB. | NOT EVALUATED |  |
| [DPL-003] | BLOCKER | B, cuando hay migraciones | Migraciones usan compatibilidad/expand-contract y declaran punto de no retorno. | Plan por release y staging test. | NOT EVALUATED |  |
| [DPL-004] | REQUIRED | A | Registrar fases aplicables: started, code/assets changed, migrations, tests, healthy, failed y rollback/recovery. | Log/registro de deploy; fases inexistentes justificadas N/A. | NOT EVALUATED |  |
| [DPL-005] | BLOCKER | A | Health y smoke aplicables pasan tras release y existe ventana de observación definida. | Resultados, versión/URL y ventana. | NOT EVALUATED |  |
| [DPL-006] | BLOCKER | A | Rollback documentado/probado para código/assets y, cuando existan, DB/config; target y criterios exactos. | Drill/runbook por componentes aplicables. | NOT EVALUATED |  |
| [DPL-007] | REQUIRED | C | Evitar irreversibilidad incompatible; usar estrategia gradual solo si el riesgo la justifica. | Plan de compatibilidad/release. | NOT EVALUATED |  |
| [DPL-008] | REQUIRED | A | Fallo parcial deja estado visible, alerta y runbook; no continúa silenciosamente. | Failure drill y salida/alerta. | NOT EVALUATED |  |
| [DPL-009] | REQUIRED | A, según stack | Permisos mínimos y caches calentadas/invalidadas conscientemente. | Revisión de permisos/cache. | NOT EVALUATED |  |
| [TEST-001] | BLOCKER | A | Cada CUF tiene happy path automatizado o smoke manual reproducible; B/C cubre fallos críticos. | Mapa CUF→tests/evidencia. | NOT EVALUATED |  |
| [TEST-002] | BLOCKER | C, para CUF/integraciones correspondientes | Probar duplicados, concurrencia, timeout, retry, fuera de orden, mismatch y dependencia caída. | Suite y resultados. | NOT EVALUATED |  |
| [TEST-003] | REQUIRED | A, cuando hay pruebas con datos/mutación | Fixtures aislados; ninguna prueba muta producción. | Config y evidencia de entorno. | NOT EVALUATED |  |
| [TEST-004] | REQUIRED | A, cuando hay CI/tests | CI bloquea fallos obligatorios; flaky tests tienen dueño/plazo. | Branch rules/CI y registro flaky. | NOT EVALUATED |  |
| [TEST-005] | REQUIRED | A, cuando existe prueba manual requerida | Pruebas manuales registran pasos, fecha, entorno, evidencia y responsable. | Acta/reporte enlazado. | NOT EVALUATED |  |
| [SEO-001] | REQUIRED | A | Cumplir módulo SEO vigente en público/híbrido; declarar/probar modo privado cuando corresponda. | Reporte SEO o evidencia de no indexación. | NOT EVALUATED |  |
| [SEO-002] | REQUIRED | A, cuando es público/híbrido | Robots, sitemap, canonical, status, redirects y enlaces corresponden al artefacto desplegado. | Smoke SEO sobre URL real. | NOT EVALUATED |  |
| [SEO-003] | REQUIRED | A, cuando existe conflicto | Registrar conflictos con Design System/SEO/seguridad; no resolverlos silenciosamente. | Registro de decisión y aprobación. | NOT EVALUATED |  |

## Cierre Production Ready

| ID | Severidad | Aplica | Verificación | Evidencia requerida | Estado | Evidencia / justificación |
| --- | --- | --- | --- | --- | --- | --- |
| [DOD-001] | BLOCKER | A | Solo declarar Production Ready cuando todos los BLOCKER y REQUIRED aplicables están PASS, ningún NOT EVALUATED se presenta como PASS, deuda recomendada tiene dueño y la aprobación identifica fecha/commit/entorno/evaluador. | Checklist firmada, matriz de evidencia y aprobación final. | NOT EVALUATED |  |

## Resultado y aprobación

- [ ] Todos los controles BLOCKER y REQUIRED aplicables están en PASS.
- [ ] Ningún NOT EVALUATED se presenta como PASS.
- [ ] Cada N/A incluye justificación verificable.
- [ ] La deuda RECOMMENDED tiene dueño y prioridad.
- [ ] Se cumplió [DOD-001].

- Resultado: PRODUCTION READY / NOT READY
- Aprobado por:
- Fecha/hora:
- Commit/artefacto:
- Condiciones de monitoreo/rollback:
