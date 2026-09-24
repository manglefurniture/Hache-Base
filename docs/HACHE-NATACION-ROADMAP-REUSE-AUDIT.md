# Auditoría de reutilización — roadmap de Hache Natación F1–F9

## Propósito y corte de evidencia

Esta auditoría separa patrones demostrados de decisiones propias de Hache Natación. No copia modelos de alumnos, profesores, cursos, pagos, sedes, Sharky ni infraestructura del proyecto fuente.

- **Fuente auditada:** `manglefurniture/hache-natacion`, `main` en `536fe3789bbf6333844e4b2f781e303d2a4cd458` (2026-09-24). El último cambio de este corte es P2-07 y no altera F1–F9.
- **Roadmap y cierres leídos:** `docs/HACHE-INTERNAL-IMPROVEMENTS-ROADMAP.md`, `F3-VERIFICATION-20260916.md`, `F4-CRM-READONLY-INCREMENT.md`, `F5-CLOSURE.md`, `F6-DASHBOARD-STATUS.md`, `F7-PROFESORES-STATUS.md`, `F8-AUDITORIA-STATUS.md` y `F9-RESUMEN-DIARIO-STATUS.md`.
- **Implementación contrastada:** los helpers, APIs y regresiones F1–F9 del árbol actual, en particular `config/centro-pendientes*.php`, `config/finanzas-obligaciones.php`, `config/sharky-crm*.php`, `config/dashboard-p06.php`, `config/profesor-actividad*.php`, `config/auditoria-unificada.php`, `config/resumen-diario*.php` y sus pruebas nombradas por fase.
- **Historial relevante contrastado:** PR/merges fuente #254/#257 (F1), #261/#262 (F2), #298 (F5), #300–#323 (F6), #326–#338 (F7), #341–#352 (F8) y #355–#357 (F9). Los commits `4a73a60` (no-op financiero), `478fc48` (telemetría fuera de auditoría), `f781cee`/`2df1497` (agregación F8 real) y `642635e` (UI F9/cobertura) confirman que los contratos respondieron a fallos/revisión reales.
- **Destino contrastado:** Hache-Base `main` en `79929be761a00604f96baf12a1bb99bd578ceb9c`, incluyendo README, catálogo, arquitectura, reglas, roles, integridad temporal, auditoría, bootstrap, Design System, Production Readiness, `src/common/`, `src/audit/`, integraciones, templates, database y tests. No existe `AGENTS.md` en ese commit; no se inventó una instrucción ausente.

El estado vigente se toma de la tabla final del roadmap y de los status/closure documents, no de párrafos históricos que describen un micro-paso anterior: F1 **Implementado**, F2 **Desplegado**, F3 **Pendiente**, F4 **Pendiente** como CRM completo (con incrementos parciales de lectura/gestión), F5 **Desplegado**, F6 **Verificado**, F7 **Desplegado**, F8 **Verificado** y F9 **Verificado**.

## Decisiones de reutilización

| Fase | Patrón | Evidencia real | Estado fuente | Equivalente Hache-Base | Gap | Decisión | Implementación |
| --- | --- | --- | --- | --- | --- | --- | --- |
| F1 | Proyección de atención separada de la causa | `pendientes_gestion`, referencias estables, no duplicación en recarga y corrección #257 de “atendido” solo cuando la causa sigue activa | Implementado | Roles/read-only y reglas genéricas, sin ficha de proyección de atención | Falta una forma reutilizable de declarar causa, estado de atención y límite de la proyección | TEMPLATE ONLY | `templates/READ-MODEL-CONTRACT.md` §5 |
| F2 | Lectura actual frente a cierre histórico | Obligaciones/pagos/cierres; PR #261/#262; el roadmap prohíbe recomputar o sobrescribir cierres | Desplegado | Integridad temporal y protección de historial financiero | Faltaba explicitar lectura viva vs snapshot para read models | EXTEND | template §4; `ESTADOS-TEMPORALES-E-INTEGRIDAD.md` §8.1 |
| F3 | Expediente compuesto con campos desconocidos | Ficha/timeline parcial; nivel, notas con autoría e historia de sede/horario siguen sin fuente decidida | Pendiente | Arquitectura y reglas de fuente única | No hay evidencia de una sección reusable más allá de composición/ausencia ya cubierta | DOCUMENT ONLY | Auditoría; sin runtime |
| F4 | Identidad, estado conversacional y oportunidad no son sinónimos | `sharky_contacts`, `contact_hash`, hitos verificables, gestión histórica y límites de estado expirado en F4 | Pendiente (CRM completo); incrementos parciales implementados | Roles, privacidad, auditoría e integraciones desacopladas | La generalización requeriría otro dominio verificado; el modelo comercial depende de Sharky | DOCUMENT ONLY | Auditoría; sin runtime |
| F5 | Detector/alerta no es autoridad ni segunda cola | Alertas reutilizan F1/F2; #298 conserva `SIN_SEDE` sin sede ficticia; pruebas de dedupe/causa/resolución | Desplegado | Reglas, observabilidad y plantillas de alertas | Faltaba separar explícitamente gestión de atención y resolución de la causa en una proyección | TEMPLATE ONLY | `templates/READ-MODEL-CONTRACT.md` §5 |
| F6 | Contrato de métricas/read model | Dashboard define fuente, unidad, periodo, anulados, cobertura; #321 forward-only; #323 UI no recalcula; validación operativa real | Verificado | Read-only, tiempo operativo y observabilidad parcial | No había contrato común que exigiera autoridad, numerador, denominador, exclusiones, corte, zona, cobertura y ausencia explícita | ADOPT | `src/common/ReadModelContract.php`; template §§2–3 |
| F6 | Desconocido no equivale a cero/PASS | Bajas, asistencia y prospectos no se publican sin cobertura/denominador; `dashboard-p06.php` devuelve no disponible | Verificado | `NOT EVALUATED` en Production Readiness, pero no en payload de métrica | Faltaba proteger la frontera de un read model | ADOPT | `ReadModelContract::metric()` y regresiones |
| F6/F9 | Implementado, desplegado y verificado son hitos distintos | Roadmap registra Quality, deploy SHA y comprobación humana por separado; F7 permanece desplegado al faltar casos reales | F6/F9 Verificado; F7 Desplegado | Production Readiness ya exige evidencia real, sin nomenclatura breve para incrementos | El delta es documental, no otro workflow o estado runtime | EXTEND | `docs/production-readiness/README.md` |
| F7 | Vigencia temporal de relaciones y sustitución explícita | PR #326–#338; asignaciones/sustituciones con inicio de cobertura; actividad confirma que carga prevista no demuestra actividad realizada | Desplegado | `DateRangeState` y reglas temporales | `DateRangeState` resuelve vigencia, no declara la cobertura de evidencia o ausencia de backfill de una proyección | EXTEND | template §4; integridad temporal §8.1 |
| F7 | Cobertura forward-only sin historia ficticia | `profesores_*_cobertura_desde`, `historia_previa_reconstruida=false`, evidencia F7.6 sin casos post-cobertura | Desplegado | No había primitive para validar ese límite en la salida de un read model | Faltaba marcador obligatorio para cobertura forward-only y distinción fuera de cobertura | EXTEND | `ReadModelContract::coverage()` y regresiones |
| F8 | Auditoría de cambio confirmado, no-op y resultado técnico | #349/`4a73a60` omite guardar sin cambios; F8.6 separa HTTP 200 de `PAGO_INVALIDADO`; #352 excluye diagnóstico; F8.5 evita dedupe heurístico | Verificado | `AuditLogger`, `AuditSanitizer`, `audit_events`, docs de auditoría | Logger no diferenciaba tipo, no suprimía snapshots equivalentes ni rechazaba scopes no administrativos | EXTEND | `src/audit/AuditLogger.php`; pruebas y docs |
| F9 | Composición read-only de autoridades | `config/resumen-diario.php`; no llama GET mutantes, expone `snapshot=false`/lectura viva y no inventa pendientes nuevos | Verificado | Regla `AUTH-RO-001` | Faltaba una plantilla para componer con corte común, cobertura y enlaces reconciliables | ADOPT | template §§2–5; reglas `VIEW-002` |
| F9 | Evidencia operacional agregada, read-only y minimizada | #357 usa `SET TRANSACTION READ ONLY`, reconcilia agregados, excluye PII y conserva `HUMAN_REVIEW_REQUIRED` | Verificado | Production Readiness ya reconoce `NOT EVALUATED` y evidencia real | Faltaba contrato ejecutable pequeño para que un collector no se autoapruebe ni oculte su frontera | ADOPT | `ReadModelContract::operationalEvidence()`; template §6 |

## F1 — Centro de pendientes

- **Problema original:** las señales de atención estaban repartidas y una señal no decía si alguien ya la había gestionado.
- **Solución final:** una proyección persistente de gestión conserva tipo, registro causante, estado de atención, responsable y fecha. F2/F5 sumaron causas sobre la misma cola, no saldos ni reglas duplicadas.
- **Decisiones/endurecimientos:** la corrección #257 evitó ofrecer “Marcar atendido” cuando ya no corresponde; prospectos sin sede se dejaron globales para ADMIN, sin una sede inventada. Recargar no genera casos duplicados.
- **Genérico:** una proyección de atención debe apuntar a una causa canónica y distinguir pendiente, atención humana y resolución demostrada.
- **Exclusivo:** tipos de pago, reposición, ausencia, prospecto, sede y permisos concretos.
- **Equivalente/delta:** Hache-Base ya impide que una lectura mutante sea implícita, pero no tenía plantilla para esta proyección. **TEMPLATE ONLY**: el contrato nuevo prohíbe que atender cambie automáticamente el registro causante.

## F2 — Finanzas internas

- **Problema original:** leer obligaciones, abonos, saldos y cierres sin alterar su identidad temporal ni reconstruir deuda con parámetros actuales.
- **Solución final:** F2 consume obligaciones/pagos válidos y cierres existentes; separa periodo de obligación, periodo financiero y fecha de cobro; los cierres guardados sobreviven como historia.
- **Decisiones/endurecimientos:** varios abonos son solo por alumno+curso intensivo, pagos invalidados permanecen como historia y el precio actual no recrea una obligación pasada.
- **Genérico:** estado actual, lectura viva y snapshot histórico no son intercambiables; una corrección posterior es un hecho nuevo.
- **Exclusivo:** conceptos financieros, abonos, P1/P15, reparto, porcentajes, convenios y PDFs.
- **Equivalente/delta:** la protección de historial financiero ya existe en Hache-Base. **EXTEND**: el contrato de read model y la guía temporal ahora obligan a etiquetar lectura viva frente a snapshot, sin crear contabilidad genérica.

## F3 — Expediente 360°

- **Problema original:** la ficha/timeline existente no acreditaba todos los datos solicitados.
- **Solución final:** no existe solución de fase completa; la fuente de nivel, notas con autoría y cobertura histórica siguen pendientes.
- **Decisiones/endurecimientos:** el roadmap prohíbe convertir horas sintéticas de presentación o estado actual en auditoría/historia exacta.
- **Genérico:** un expediente compuesto debe conservar fuente, fecha disponible y ausencia explícita.
- **Exclusivo:** alumno, nivel académico, pagos, asistencia, reposiciones y notas internas.
- **Equivalente/delta:** `VIEW-002`/`VIEW-003` cubren la base de composición y ausencia. **DOCUMENT ONLY** porque F3 no está implementada ni verificada y no justifica un módulo “expediente” base.

## F4 — CRM interno / Sharky

- **Problema original:** contacto, identidad, estado conversacional, hito comercial y oportunidad no eran un CRM completo ni equivalían entre sí.
- **Solución final:** incrementos de lectura muestran solo hitos verificables; la gestión interna usa `contact_hash`, anclas temporales/contadores e historial propio sin dirigir el funnel, mensajes, takeover o pagos.
- **Decisiones/endurecimientos:** estado expirado deja producto/sede como desconocidos; una acción `COMPLETED` acredita inscripción, no un flow abierto. La gestión no reabre follow-up ni crea pendientes automáticamente.
- **Genérico:** conservar autoridad de identidad y distinguir un hecho confirmado de una inferencia.
- **Exclusivo:** Sharky, hash/contacto, WhatsApp, fuentes comerciales, funnel, reglas de elegibilidad y estados de CRM.
- **Equivalente/delta:** privacidad, audit trail, roles y desacoplamiento de integraciones de Base ya son la parte reusable. **DOCUMENT ONLY**: la fase completa sigue pendiente y un CRM universal excedería la evidencia de un solo dominio.

## F5 — Alertas internas

- **Problema original:** cubrir señales de atención con una regla explicable sin abrir una segunda cola ni aplicar acciones automáticas.
- **Solución final:** reglas deterministas reutilizan las autoridades de F1/F2; la alerta explica causa, periodo y resolución, mientras F1 conserva la gestión.
- **Decisiones/endurecimientos:** umbrales siguen configurables/project-owned; la continuidad sin política queda deshabilitada; datos incompletos no se convierten en incumplimiento; #298 mantiene prospectos sin sede como globales.
- **Genérico:** detección, atención y resolución de causa son responsabilidades distintas.
- **Exclusivo:** umbrales, prioridades, absentismo, continuidad, cobertura de pagos, productos y mensajes.
- **Equivalente/delta:** alertas accionables P2-02 ya cubren señales/runbooks, pero no una proyección de atención sobre la causa. **TEMPLATE ONLY** mediante la sección de asuntos del contrato; no se crea un ticketing universal.

## F6 — Dashboard operativo

- **Problema original:** cifras operativas podían tener definiciones, cortes y coberturas implícitos o divergentes.
- **Solución final:** cada bloque declara fuente, periodo, sede, definición y detalle reconciliable. Prospectos/conversión usan lifecycle durable, cohorte y cobertura forward-only; la UI consume el contrato sin recalcularlo.
- **Decisiones/endurecimientos:** #310 se dividió por problemas reales de identidad/lifecycle/idempotencia; #316 exigió inscripción `COMPLETED` y vínculo exacto; #321 añadió cobertura; #323 preservó `SIN_SEDE`/`SIN_FUENTE` y no hizo backfill.
- **Genérico:** contrato de métrica, `0` medido frente a desconocido, autoridad única y cobertura publicada.
- **Exclusivo:** definición de activo, alumno, conversión, periodo financiero, fuentes/estados comerciales y sedes.
- **Equivalente/delta:** Base tenía read-only, zona horaria y observabilidad, pero no una frontera de métrica/read model. **ADOPT**: `ReadModelContract` exige los campos del contrato y rechaza un cero cuando la evidencia no está disponible.

## F7 — Gestión de profesores

- **Problema original:** una relación actual de horario no demostraba quién impartió una actividad pasada; sustitución, docencia compartida e inactivación requerían historia propia.
- **Solución final:** asignaciones y sustituciones son explícitas y forward-only; la lectura separa carga prevista, confirmada, no impartición y falta de atribución. F7.6 encontró evidencia agregada sin casos reales post-cobertura, por eso no se sobrerreclama verificación.
- **Decisiones/endurecimientos:** una cancelación individual no cancela una actividad compartida; no se reconstruyen sustituciones desde cancelaciones; la corrección #338 trata inconsistencias legacy sin borrar filas ni inventar historia.
- **Genérico:** relaciones con vigencia y cobertura de captura necesitan un inicio explícito, y carga prevista no equivale a actividad confirmada.
- **Exclusivo:** profesor, horario, clase, sustitución, carga docente y reglas de docencia compartida.
- **Equivalente/delta:** `DateRangeState` cubre el intervalo de vigencia, no la cobertura de evidencia. **EXTEND**: `ReadModelContract::coverage()` exige inicio en forward-only y declara `history_reconstructed`; no crea tablas temporales genéricas.

## F8 — Auditoría administrativa

- **Problema original:** las fuentes existentes no acreditaban una historia uniforme y una respuesta técnica correcta podía confundirse con un cambio confirmado.
- **Solución final:** F8 proyecta fuentes administrativas read-only, conserva actor/entidad/timestamp y snapshots durables cuando existen, separa resultado técnico de cambio de dominio y no correlaciona/deduplica por heurística.
- **Decisiones/endurecimientos:** #349 corrigió guardados sin cambio; F8.5 extrajo la agregación real tras una revisión que detectó una prueba decorativa; #352 sacó diagnóstico/telemetría del audit administrativo; F8.6 comprobó en producción el par HTTP 200 + invalidación durable.
- **Genérico:** no-op no genera cambio, snapshots solo tienen sentido para cambio confirmado, diagnóstico/read-only no pertenece a audit administrativo, y actor/contexto/entidad no se inventan.
- **Exclusivo:** acciones, tablas, roles y proyección de auditoría de Hache Natación.
- **Equivalente/delta:** Base ya tenía `AuditLogger`, `AuditSanitizer` y `audit_events`. **EXTEND**: no se crea un sistema nuevo; el logger ahora descarta no-ops, separa `domain_change` de `technical_result`, rechaza scopes no administrativos y sanitiza snapshots.

## F9 — Resumen operativo diario

- **Problema original:** la operación necesitaba consumir varias autoridades sin que consultar generara sesiones, reconciliaciones, cierres ni un sistema autoritativo nuevo.
- **Solución final:** F9 compone fuentes puras con fecha/corte explícito y lectura viva/reconciliable; marca pendiente nuevo como no disponible sin una primera detección durable. F9.3 ejecuta evidencia agregada en transacción read-only, reconcilia y minimiza datos.
- **Decisiones/endurecimientos:** se evitaron APIs GET que mutan, se distinguieron sesiones canceladas, validez/fecha de cobro y planificación histórica no disponible. La UI fue corregida para no ofrecer enlaces mutantes/no autorizados y para conservar la cobertura F7.
- **Genérico:** composición de read models, corte común, lectura verdaderamente read-only, casos vacíos válidos, ausencia explícita y collector que no se autoaprueba.
- **Exclusivo:** fecha operativa de Cancún, bloques de apertura/cierre, sesiones, cobros, alumnos, sedes y permisos concretos.
- **Equivalente/delta:** `AUTH-RO-001` ya prohibía efectos laterales, y Production Readiness ya preservaba `NOT EVALUATED`. **ADOPT**: la primitive y plantilla convierten ese principio en una frontera de payload/evidencia sin crear dashboard, collector central, snapshots ni infraestructura.

## Patrones ya cubiertos o rechazados

### ALREADY COVERED

- Arquitectura **Core → Theme → Extensions**: ninguno de los hallazgos requiere una capa paralela; las adiciones son Core mínimo (`ReadModelContract`), extensión del audit Core y plantilla opt-in.
- Autorización server-side, contexto y consultas read-only: `docs/ROLES-Y-PERMISOS.md` y `AUTH-RO-001` ya lo exigen; el delta solo lo hace operativo para read models compuestos.
- `DateRangeState` y zona horaria explícita: siguen siendo la primitive de vigencia; no se duplicó para relaciones de profesores.
- Estados `NOT EVALUATED` y prohibición de auto-PASS: Production Readiness ya los define; el nuevo collector conserva esa semántica en su frontera.
- Inbox/outbox, idempotencia, observabilidad, deploy/restore evidence y review/PR discipline: las lecciones F1–F9 no demuestran un hueco que justifique otra implementación.

### REJECT

- Entidades/rules de alumnos, profesores, cursos, horarios, clases, ausencias, reposiciones, mensualidades, periodos P1/P15, pagos/abonos y reparto financiero.
- Sharky, WhatsApp, campañas/fuentes, funnel, estados comerciales, takeover, conversiones y modelos CRM específicos.
- Sedes Monteverde/Palapas, PROA, porcentajes, mínimos, horarios, prioridades y thresholds de alertas.
- SQL del dominio fuente, backfills para producir cobertura, snapshots ficticios y marcadores que atribuyan acciones antiguas sin evidencia.
- Redis, queues, shared store, VPS, SaaS, P3 y P2-05: ninguna fase demuestra una necesidad reusable adicional; P2-05 permanece explícitamente no iniciado en Hache-Base.

## Implementación resultante y límites

Los hallazgos `ADOPT`, `EXTEND` y `TEMPLATE ONLY` de la matriz se implementan en este cambio. Los `DOCUMENT ONLY`, `ALREADY COVERED` y `REJECT` no reciben runtime adicional.

La implementación no introduce migraciones, tablas, dependencias, proveedores, defaults de negocio ni datos de Hache Natación. Los tests cubren: cero medido vs evidencia ausente, marcador forward-only, collector read-only con revisión humana, no-op de auditoría, resultado técnico separado, exclusión de scopes diagnósticos y ausencia de vocabulario específico del proyecto en el runtime reusable.
