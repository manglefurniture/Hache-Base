# HACHE BASE — PRODUCTION READINESS NORMALIZATION REPORT

**Fecha:** 1 de septiembre de 2026  
**Alcance:** normalización documental exclusivamente  
**Fuente de verdad:** `PRODUCTION-READINESS-STANDARD.md` v1.1  
**Runtime, funcionalidades, dependencias, migraciones y deploy:** no modificados

---

## 1. Resultado

La normalización produjo un **registro canónico de 126 controles** en la sección 24 del Standard. Cada control contiene:

- ID estable;
- regla verificable;
- severidad;
- nivel mínimo o condición explícita;
- evidencia mínima;
- potencial de automatización;
- necesidad de revisión humana.

La Checklist fue reconstruida como representación directa de ese registro. Contiene exactamente los mismos 126 IDs y copia literalmente severidad, aplicabilidad, regla y evidencia. No conserva reglas independientes.

Estados admitidos: `PASS`, `FAIL`, `N/A` y `NOT EVALUATED`. `NOT EVALUATED` nunca equivale a PASS. N/A exige justificación verificable.

## 2. Inconsistencias estructurales detectadas

| Inconsistencia | Estado anterior | Corrección |
| --- | --- | --- |
| Falta total de trazabilidad | Ningún check incluía ID normativo. | Cada fila de Checklist incluye `[ID]`; coincidencia 126/126 con Standard. |
| Checklist como segunda norma | Dividía o combinaba reglas y asignaba severidad propia. | Checklist proyecta la fila canónica, sin reinterpretación. |
| Reglas narrativas sin nivel | Varias reglas indicaban solo REQUIRED/BLOCKER o “cuando aplica”. | Registro canónico fija nivel mínimo y condición. |
| Evidencia incompleta | Algunas secciones solo nombraban el control. | Todas las filas canónicas declaran evidencia mínima. |
| N/A binario/ambiguo | El checkbox no distinguía falta de evaluación. | Se separan PASS/FAIL/N/A/NOT EVALUATED. |
| Perfil A sobredimensionado | No estaba claro cuándo DB, RPO/RTO, COM o WH eran N/A. | Baseline A explícito; controles especializados son condicionales. |
| Automatización futura no estructurada | Había oportunidades generales sin metadata por control. | Cada control marca automatización Sí/Parcial/No y revisión humana. No se creó schema/runtime. |

## 3. Correcciones normativas específicas

“Checklist anterior” reproduce el sentido/severidad anterior, no pretende conservar su redacción completa.

| ID | Regla Standard original | Checklist anterior | Corrección realizada | Severidad/nivel definitivo |
| --- | --- | --- | --- | --- |
| GOV-001 | Clasificar A/B/C era obligatorio pero no tenía ID/severidad propios. | BLOCKER A para declarar nivel. | Se formalizó el control de clasificación. | **BLOCKER — A** |
| GOV-002 | Inventario obligatorio dentro de “todo proyecto DEBE mantener”. | Inventario y CUF figuraban como BLOCKER A separados. | Inventario se mantiene obligatorio sin elevarlo artificialmente a blocker. | **REQUIRED — A** |
| GOV-003 | Matriz CUF obligatoria sin ID propio. | Varios checks REQUIRED/BLOCKER por contenido del CUF. | Se unificó la matriz; controles de idempotencia siguen en ROB/WH/TEST. | **REQUIRED — A** |
| GOV-004 | N/A no estaba normalizado. | Solo exigía justificación; no existía NOT EVALUATED. | Se formalizaron cuatro estados y se bloquea el uso abusivo de N/A. | **BLOCKER — A** |
| A11Y-008 | REQUIRED “cuando aplica”. | REQUIRED B, aunque una landing A también puede usar modal. | Aplicabilidad por capacidad, no por complejidad general. | **REQUIRED — A cuando hay modales** |
| SEC-001 | BLOCKER B/C; REQUIRED A. | Dividió HSTS e hizo `includeSubDomains` BLOCKER A. | Se volvió a la severidad mixta del Standard y se exige evidencia de subdominios. | **REQUIRED A; BLOCKER B/C** |
| SEC-003 | REQUIRED B/C; RECOMMENDED A. | Solo mostraba REQUIRED B. | Se restauró la recomendación explícita para A. | **RECOMMENDED A; REQUIRED B/C** |
| SEC-008 | BLOCKER C; REQUIRED B. | BLOCKER B para login/recuperación. | Se eliminó la elevación en B y se preservó bloqueo C. | **REQUIRED B; BLOCKER C** |
| SEC-011 | BLOCKER C; REQUIRED B cuando aplica. | BLOCKER B para uploads. | Se corrigió la elevación de B; condición upload explícita. | **REQUIRED B; BLOCKER C, cuando hay uploads** |
| SEC-014 | BLOCKER B/C; REQUIRED A. | Mostraba solo BLOCKER B. | Se hizo visible el baseline A y el bloqueo B/C. | **REQUIRED A; BLOCKER B/C** |
| ROB-002 | BLOCKER C / REQUIRED B. | BLOCKER B para interpretar `2xx`. | Se restauró severidad mixta. | **REQUIRED B; BLOCKER C, cuando confirmación es posterior** |
| ROB-003 | BLOCKER C; REQUIRED B. | BLOCKER B para timeout. | Se corrigió B y se mantuvo bloqueo C. | **REQUIRED B; BLOCKER C, cuando hay llamadas externas** |
| ROB-004 | BLOCKER C; REQUIRED B. | REQUIRED B; no preservaba bloqueo C. | Se añadió el bloqueo C sin elevar B. | **REQUIRED B; BLOCKER C, cuando hay retry** |
| ROB-006 | BLOCKER C; REQUIRED B. | BLOCKER C solamente en un check y efecto secundario sin requisito B claro. | Se explicitó el requisito B y bloqueo C. | **REQUIRED B; BLOCKER C, cuando hay efectos secundarios** |
| ROB-008 | BLOCKER C; REQUIRED B cuando crítico. | BLOCKER C; omitía requisito B. | Se formalizó en B cuando existen estados pendientes/retryables. | **REQUIRED B; BLOCKER C** |
| COM-001 | BLOCKER C / REQUIRED B. | BLOCKER B. | Se eliminó elevación de B. | **REQUIRED B; BLOCKER C, cuando hay comunicación transaccional** |
| COM-002 | REQUIRED. | Añadió un check BLOCKER B para no confundir `sent` con entregado. | El principio permanece dentro del mismo control sin elevar severidad. | **REQUIRED B, cuando proveedor ofrece estados** |
| COM-005 | REQUIRED C. | BLOCKER C para fallback. | Se corrigió la elevación. | **REQUIRED — C, cuando comunicación integra el CUF** |
| WH-002 | BLOCKER C; REQUIRED B. | BLOCKER C; omitía B. | Se añadió requisito B y se preservó bloqueo C. | **REQUIRED B; BLOCKER C** |
| WH-004 | BLOCKER C; REQUIRED B. | BLOCKER C; omitía B. | Se añadió requisito B y condición de eventos fuera de orden. | **REQUIRED B; BLOCKER C** |
| WH-006 | BLOCKER C; REQUIRED B cuando crítico. | BLOCKER C; omitía B. | Se formalizó B cuando webhook es reintentable/crítico. | **REQUIRED B; BLOCKER C** |
| DB-002 | BLOCKER C / REQUIRED B. | BLOCKER B. | Se eliminó elevación de B. | **REQUIRED B; BLOCKER C, cuando hay DB** |
| DB-009 | REQUIRED C. | BLOCKER C. | Se corrigió la elevación. | **REQUIRED — C, cuando hay evidencia financiera/histórica** |
| CFG-004 | REQUIRED sin nivel explícito. | Startup seguro como BLOCKER A y cambios auditables como REQUIRED B. | Se reunificó y se evitó exigir startup a una landing estática. | **REQUIRED — B, cuando hay runtime/config mutable** |
| DPL-002 | BLOCKER, sin baseline A detallado. | Preflight A exigía backup sin distinguir ausencia de DB. | Sigue bloqueando el deploy, pero los checks de DB/backup son N/A si no existen. | **BLOCKER — A, componentes aplicables** |
| DPL-004 | REQUIRED sin nivel explícito. | REQUIRED B. | Se hizo aplicable a A con fases reducidas: code/assets/health/fallo; migraciones N/A. | **REQUIRED — A** |
| DPL-006 | BLOCKER, rollback general. | Código A y DB/assets/config B aparecían separados. | Código/assets continúan A; DB/config solo si existen. | **BLOCKER — A, componentes aplicables** |
| DPL-008 | REQUIRED sin nivel explícito. | REQUIRED B. | Un deploy A también debe dejar fallo visible; no requiere plataforma compleja. | **REQUIRED — A** |
| OBS-001 | BLOCKER B/C; REQUIRED A con servicio dinámico. | Solo BLOCKER B. | Se restauró la obligación condicional A sin exigir logging a estático puro. | **REQUIRED A dinámico; BLOCKER B/C** |
| OBS-005 | BLOCKER C; REQUIRED B. | La Checklist lo dividía entre liveness/readiness REQUIRED B y health BLOCKER C/REQUIRED B. | Se unificó sin cambiar severidad. | **REQUIRED B; BLOCKER C, servicio dinámico** |
| DEP-003 | BLOCKER B/C. | BLOCKER B. | Se aclaró que B es nivel mínimo y por tanto también C; no se extendió a A. | **BLOCKER — B cuando hay dependencias** |
| TEST-001 | BLOCKER A/B/C. | BLOCKER A, con checks B adicionales no trazados. | Se conserva un único control y la exigencia B/C de fallos críticos dentro de él. | **BLOCKER — A** |
| DOD-001 | Definition of Done era una lista sin ID. | Resultado PRODUCTION READY/NOT READY sin vínculo. | Se creó control de cierre único y trazable. | **BLOCKER — A** |

## 4. Normalización de aplicabilidad

Se asignaron condiciones explícitas a controles anteriormente abreviados:

- imágenes, fuentes, preload, terceros y multimedia: solo si existen;
- auth, sesión y autorización: Nivel B cuando existen cuentas/recursos protegidos;
- formularios: B cuando el proyecto los incorpora;
- comunicaciones: B/C cuando son transaccionales;
- webhooks: B/C cuando se reciben;
- DB, migración, backup/restore y RPO/RTO: B/C cuando hay datos persistentes no reproducibles;
- liveness/readiness/logs operativos: cuando existe servicio dinámico;
- privacy: cuando se tratan datos personales o trackers;
- deploy/rollback/smoke: siempre A, adaptados al stack real.

Esto no permite degradar un proyecto: una landing con formulario o persistencia deja de ser A según la clasificación del Standard.

## 5. Verificación exhaustiva

### 5.1 Corrección final de accesibilidad

Se detectó que la sección `## Accesibilidad` de la Checklist conservaba únicamente el encabezado de tabla. Aunque el informe anterior declaraba paridad, aquella validación produjo un falso positivo al no limitar la comparación a filas normativas efectivas.

| Inconsistencia detectada | Standard original | Checklist anterior | Corrección realizada | Severidad/nivel definitivo |
| --- | --- | --- | --- | --- |
| A11Y-001…A11Y-012 ausentes como controles verificables | Registro canónico §24.4 con doce reglas normativas | Tabla de Accesibilidad vacía | Se incorporaron literalmente las doce filas, preservando ID, regla, severidad, aplicabilidad y evidencia mínima | Exactamente el definido individualmente por A11Y-001…A11Y-012 en §24.4 |

No se modificó ninguna regla del Standard ni se introdujo interpretación normativa adicional.

### 5.2 Resultado de la comprobación final

Se ejecutaron comprobaciones documentales sobre filas normativas y columnas normalizadas:

1. 126 IDs únicos en el registro canónico del Standard.
2. 126 filas normativas con IDs únicos en la Checklist.
3. Diferencia de conjuntos Standard↔Checklist: cero.
4. Severidad por ID: coincidencia literal.
5. Aplicabilidad por ID: coincidencia literal.
6. Regla/verificación por ID: coincidencia literal.
7. Evidencia requerida por ID: coincidencia literal.
8. No existen IDs duplicados ni controles contradictorios.
9. Cada fila inicia en `NOT EVALUATED`.
10. Los únicos estados admitidos continúan siendo `PASS`, `FAIL`, `N/A` y `NOT EVALUATED`; `NOT EVALUATED` nunca equivale a PASS.
11. Roadmap conserva P0/P1/P2/P3.
12. Primera fase futura permanece limitada a P0-01, P0-02, P0-03, P0-04 y P0-09.
13. Research Sources conserva ASVS 5.0.0, WCAG 2.2, Core Web Vitals actuales y RFC 9110/9111/9112; no hubo cambio de versión.

## 6. Ambigüedades restantes

No queda ninguna diferencia normativa de severidad o aplicabilidad entre Standard y Checklist.

Permanecen decisiones humanas intencionales, sin alterar metadatos:

- si existe suficiente volumen/ventana de datos de campo para PERF-001;
- si una excepción WCAG o target aplica correctamente;
- riesgo, alcanzabilidad y control equivalente en seguridad;
- obligaciones legales de privacidad/retención por jurisdicción;
- vigencia aceptable de restore drills, RTO/RPO y ventanas de observación;
- si un tercero o CUF eleva un módulo a Nivel C.

Estas decisiones deben resolverse con evidencia y dueño. Mientras no se evalúen, su estado es NOT EVALUATED, no PASS ni N/A.

## 7. Cambios realizados por archivo

- `PRODUCTION-READINESS-STANDARD.md`: v1.1, registro canónico, baseline A, estados y metadata futura machine-readable.
- `PRODUCTION-READINESS-CHECKLIST.md`: reconstruida desde los 126 controles canónicos y corregida para incluir A11Y-001…A11Y-012.
- `PRODUCTION-READINESS-AUDIT.md`: referencias por ID y nota de normalización.
- `PRODUCTION-READINESS-ROADMAP.md`: Standard como fuente, P0-01 actualizado y primera fase preservada.
- `RESEARCH-SOURCES.md`: nota de normalización; fuentes/versiones sin cambios.
- `PRODUCTION-READINESS-NORMALIZATION-REPORT.md`: este informe.

## 8. Estado final

Normalización documental completada. No se implementó ningún control. El siguiente paso requiere autorización explícita.
