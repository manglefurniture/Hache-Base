# HACHE BASE — PRODUCTION READINESS STANDARD

**Estado:** Norma normalizada candidata a aprobación v1.1  
**Fecha:** 1 de septiembre de 2026  
**Ámbito:** Proyectos web construidos con Hache Base  
**Arquitectura:** `Core → Theme → Extensions`  
**Principio rector:** Hache Base estandariza calidad, no apariencia.

---

## 0. Propósito y límites

Este estándar define la evidencia mínima necesaria para afirmar que un proyecto está preparado para producción. No sustituye `DESIGN-SYSTEM-2026-FINAL.md` ni `seo/`; los referencia como normas especializadas.

Production Ready significa **estado demostrable**, no que el build terminó, la página abrió una vez o una API devolvió `200`.

Esta norma no obliga a una landing a implementar la arquitectura operativa de una plataforma de pagos. Los controles se aplican según riesgo, datos y efectos del proyecto.

## 1. Lenguaje normativo y severidad

- **DEBE / MUST:** requisito verificable obligatorio cuando aplica.
- **DEBERÍA / SHOULD:** recomendación fuerte. Su omisión exige una razón registrada.
- **PUEDE / MAY:** opcional.

| Severidad | Significado | Efecto |
| --- | --- | --- |
| **BLOCKER** | Riesgo inmediato de seguridad, pérdida/corrupción de datos, operación crítica incorrecta o imposibilidad de recuperar el servicio. | Impide declarar Production Ready. No admite renuncia; solo evidencia de no aplicabilidad o control equivalente. |
| **REQUIRED** | Baseline obligatorio aplicable. | Impide declarar Production Ready hasta cumplirlo. |
| **RECOMMENDED** | Mejora importante de calidad o reducción de riesgo. | No bloquea, pero su omisión se registra con dueño. |
| **OPTIONAL** | Capacidad contextual. | No afecta el estado. |

Una excepción no convierte un incumplimiento en cumplimiento. Solo es válida si demuestra que el requisito no aplica o que existe un control equivalente con evidencia, dueño y fecha de revisión.

### 1.1 Fuente normativa y estructura de control

Este documento es la única fuente normativa de Production Readiness. Cada regla evaluable tiene un ID estable y una fila en el **Registro canónico de controles** de la sección 24. El registro define obligatoriamente:

- ID;
- severidad;
- nivel mínimo o condición de aplicabilidad;
- evidencia requerida;
- potencial de automatización;
- necesidad de revisión humana.

Las explicaciones de las secciones 5–23 aportan contexto. Si una síntesis narrativa pudiera interpretarse de forma distinta, prevalece la fila del registro canónico. La Checklist reproduce ese registro y no puede elevar, reducir ni reinterpretar sus metadatos.

### 1.2 Estados de evaluación

- **PASS:** evidencia suficiente y vigente demuestra cumplimiento.
- **FAIL:** evidencia demuestra incumplimiento o control incompleto.
- **N/A:** el control realmente no aplica y existe justificación verificable.
- **NOT EVALUATED:** no se ha reunido evidencia suficiente. Nunca equivale a PASS.

Un control incómodo, costoso o todavía no implementado no es N/A por esas razones.

## 2. Clasificación de riesgo

El proyecto declara un nivel antes de desarrollar los Critical User Flows. Si reúne condiciones de varios niveles, usa el mayor.

| Nivel | Perfil | Ejemplos | Baseline |
| --- | --- | --- | --- |
| **A — Informativo** | Contenido principalmente de lectura, sin cuentas, persistencia de negocio ni mutaciones remotas; un enlace externo no eleva el nivel. | Landing, portafolio, sitio corporativo. | Disponibilidad, seguridad HTTP, accesibilidad, SEO si es público, performance, errores, deploy/rollback de assets. |
| **B — Interactivo** | Formularios, cuentas, sesiones, datos personales, persistencia o automatizaciones no financieras. | Registro, reservas sin pago, CRM, panel, inscripción. | Nivel A + validación servidor, autorización, CSRF según mecanismo, auditoría proporcional, backups, observabilidad y resiliencia de integraciones. |
| **C — Crítico** | Pagos, inventario/cupo crítico, datos sensibles, efectos legales/financieros, integraciones que cambian estado o procesos cuya duplicación/pérdida causa daño material. | Ecommerce, cobros, conciliación, plataforma operativa crítica. | Nivel B + idempotencia persistente, reconciliación, outbox/cola cuando proceda, restore probado, alertas, rollback compatible y pruebas de concurrencia/fallo. |

El nivel puede elevarse por una sola ruta o módulo. Ese módulo se trata como C sin obligar al resto del sitio a adoptar complejidad innecesaria.

### 2.1 Baseline explícito de Nivel A

Un proyecto A sencillo DEBE poder ser Production Ready sin inventar infraestructura que no utiliza. Su baseline incluye: alcance/CUF de lectura o navegación, seguridad HTTP, performance, accesibilidad, manejo seguro de errores, dependencias/configuración que realmente existan, deploy del artefacto exacto, rollback de código/assets, health o smoke representativo y SEO cuando sea público.

En Nivel A son **N/A con justificación** cuando no existe la capacidad correspondiente:

- migraciones, backup/restore y RPO/RTO de datos si no hay DB ni persistencia;
- formularios si no hay formularios;
- comunicaciones transaccionales si no se envían;
- webhooks si no se reciben;
- sesión, autenticación y autorización si no existen cuentas o áreas protegidas;
- uploads si no se aceptan archivos;
- estados asíncronos de negocio si no hay operaciones externas con efecto relevante.

Analytics, CDN, formularios externos o terceros sí deben inventariarse y evaluarse en los controles que correspondan; llamarlos “externos” no los vuelve N/A.

## 3. Ubicación arquitectónica

- **CORE:** contrato transversal, primitive ligera, plantilla, test o guardrail útil en todos o casi todos los proyectos. No implica activar runtime especializado.
- **THEME:** presentación configurable: identidad, tokens, tipografía, color, densidad, movimiento y assets visuales.
- **EXTENSION:** capacidad especializada, opt-in y removible: pagos, proveedor de correo/WhatsApp, colas, storage, captcha, observabilidad avanzada, uploads, WebGL.
- **PROJECT RESPONSIBILITY:** configuración, reglas, contenido, amenazas, flujos, métricas, proveedores, infraestructura y evidencia reales del proyecto.

Una práctica general no entra automáticamente al Core. Para promoverla debe ser reusable, pequeña, estable, configurable, probada y no imponer infraestructura a proyectos que no la necesitan.

## 4. Evidencia y Critical User Flows

### 4.1 Inventario obligatorio

Todo proyecto DEBE mantener:

1. nivel A/B/C y justificación;
2. URLs/servicios desplegados;
3. datos y secretos manejados;
4. dependencias e integraciones;
5. **Critical User Flows (CUF)**;
6. dueño técnico y dueño de negocio de cada CUF;
7. pruebas y señales operativas asociadas;
8. procedimiento de recuperación.

Un CUF es un recorrido cuya falla impide el objetivo principal, pierde datos, duplica efectos, bloquea ingresos/acceso o produce estado incorrecto. Ejemplos: registro, login, recuperación, formulario, reserva, inscripción, compra, pago y webhook.

### 4.2 Matriz mínima de CUF — REQUIRED A/B/C

Cada CUF DEBE registrar: precondición, pasos, resultado observable, mutaciones, integraciones, estados de fallo, idempotency key si aplica, prueba automatizada, smoke de producción y eventos/logs que permiten reconstruirlo.

Los controles canónicos de gobierno son `GOV-001` a `GOV-004`; su severidad, nivel y evidencia se encuentran en la sección 24.

### 4.3 Calidad de evidencia

| Evidencia | Qué demuestra | Qué no demuestra |
| --- | --- | --- |
| Revisión estática | Configuración, contratos, ausencia/presencia de patrones. | Comportamiento real. |
| Unit/integration test | Regla o interacción controlada. | Disponibilidad del entorno real. |
| E2E/smoke | Recorrido desplegado. | Entrega de terceros posterior al ACK. |
| Telemetría de campo | Experiencia/operación real. | Causa sin correlación adicional. |
| Restore drill | Recuperabilidad. | Que futuros backups sean correctos sin monitoreo. |

## 5. Modelo de estado para operaciones asíncronas

**ROB-001 — BLOCKER B/C — CORE contract + PROJECT RESPONSIBILITY**  
Toda operación externa con efecto relevante DEBE distinguir como mínimo:

- `INITIATED`: solicitud local aceptada;
- `PROCESSING`: trabajo pendiente o proveedor aceptó procesar;
- `CONFIRMED`: resultado autoritativo confirmado;
- `FAILED`: fallo definitivo;
- `RETRYABLE`: fallo temporal elegible para reintento;
- `CANCELLED`: cancelación explícita;
- `UNKNOWN`: resultado incierto que requiere reconciliación.

Los nombres pueden cambiar, pero no se puede colapsar “solicitud enviada” y “operación completada”. Cada transición DEBE definir actor, condición, timestamp, terminalidad y si permite retry.

**ROB-002 — BLOCKER C / REQUIRED B**  
Una respuesta `2xx` de un proveedor solo confirma lo que su contrato diga. Si representa aceptación, el estado local no DEBE marcarse como entregado/pagado/completado sin evidencia autoritativa posterior.

## 6. Performance

Esta sección complementa el Design System. Los límites de Core Web Vitals no son arbitrarios: corresponden a la clasificación “good” de Google, evaluada idealmente en percentil 75.

| ID | Regla | Severidad/aplica | Evidencia | Dueño |
| --- | --- | --- | --- | --- |
| PERF-001 | LCP ≤ 2.5 s, INP ≤ 200 ms y CLS ≤ 0.1 en p75 para móvil y desktop cuando exista tráfico de campo suficiente. | REQUIRED A/B/C | CrUX/RUM por plantilla/CUF y ventana documentada. | Project |
| PERF-002 | Antes de disponer de campo, medir páginas/CUF representativos en laboratorio, móvil limitado y build de producción; registrar LCP/INP proxy/TBT/CLS y causas. | REQUIRED A/B/C | Reporte versionado de Lighthouse u herramienta equivalente. | Project |
| PERF-003 | Lighthouse no se usa como sustituto de campo ni se impone un score único universal. Un descenso material contra baseline exige investigación. | REQUIRED A/B/C | Comparación con baseline. | Core policy + Project |
| PERF-004 | Definir presupuesto por proyecto para JS, CSS, imágenes, fuentes y terceros antes del release. El límite se justifica por baseline, CUF y dispositivo, no por una cifra copiada. | REQUIRED A/B/C | `PERFORMANCE-BUDGET` completado y CI cuando sea estable. | Core template + Project |
| PERF-005 | Imágenes con dimensiones o `aspect-ratio`; `srcset`/`sizes` cuando se sirven tamaños distintos; AVIF/WebP cuando reduce peso sin degradación inaceptable; fallback cuando proceda. | REQUIRED A/B/C | Inspección de markup/network. | Component + Theme/Project content |
| PERF-006 | No aplicar lazy loading al recurso LCP si retrasa su descubrimiento. Imágenes/iframes fuera de viewport DEBERÍAN diferirse. | REQUIRED A/B/C | Waterfall y elemento LCP identificado. | Component/Project |
| PERF-007 | `preload` solo para recursos críticos comprobados; cada preload debe consumirse pronto, con tipo/crossorigin correctos. | REQUIRED A/B/C | Network sin preload ocioso/duplicado. | Project |
| PERF-008 | Fuentes: variantes usadas únicamente, WOFF2 cuando sea viable, estrategia `font-display`, fallback métrico y ausencia de shifts materiales. | REQUIRED A/B/C | Network + CLS + CSS. | Theme/Project |
| PERF-009 | JS/CSS no usado, render-blocking y tareas largas se reducen o difieren según impacto; el JS decorativo no bloquea CUF. | REQUIRED A/B/C | Coverage/waterfall/long tasks. | Core/Extension/Project |
| PERF-010 | Terceros tienen dueño, propósito, datos compartidos, coste medido, timeout/fallback y criterio de retiro. | REQUIRED A/B/C | Inventario y medición con/sin tercero. | Extension/Project |
| PERF-011 | Compresión HTTP y caché se configuran por tipo: assets versionados pueden ser inmutables; HTML/API/datos privados usan políticas explícitas; nunca cachear respuestas sensibles por accidente. | REQUIRED A/B/C | Headers reales y prueba de invalidación. | Core template + Project infra |
| PERF-012 | La prueba incluye red lenta, CPU limitada y al menos un dispositivo móvil representativo; desktop rápido no basta. | RECOMMENDED A/B/C | Perfil de ejecución registrado. | Project |

Métricas **obligatorias:** PERF-001 cuando hay campo; PERF-002 mientras no lo haya; presupuesto y regresión. **Recomendadas:** métricas diagnósticas como TTFB, FCP, TBT, long tasks, peso y requests. **Informativas:** score agregado de Lighthouse y métricas sin vínculo a un CUF, salvo que el proyecto las convierta en presupuesto.

## 7. Accesibilidad

Objetivo mínimo: WCAG 2.2 AA. La conformidad requiere evaluación automática **y humana**; ninguna herramienta automática prueba WCAG completa.

| ID | Regla | Severidad | Dueño |
| --- | --- | --- | --- |
| A11Y-001 | Declarar `lang`, landmarks, título, headings y orden DOM lógico. | REQUIRED A/B/C | Core contract + Project content |
| A11Y-002 | Todas las acciones y CUF son operables por teclado sin trampa; el foco sigue el orden y propósito. | BLOCKER B/C; REQUIRED A | Component + Project |
| A11Y-003 | `focus-visible` perceptible y no totalmente oculto por sticky/overlays. | REQUIRED A/B/C | Core + Theme/Project |
| A11Y-004 | Controles tienen nombre accesible; labels visibles en formularios; ARIA solo cuando HTML nativo no expresa el patrón y nunca contradice estado real. | BLOCKER B/C; REQUIRED A | Component + Project |
| A11Y-005 | Errores identifican campo, causa y corrección; resumen/enfoque cuando sea necesario; éxito/error no depende solo de color. | REQUIRED B/C | Component + Project |
| A11Y-006 | Contraste cumple WCAG 2.2 AA en cada Theme/estado; Core solo puede garantizar fallbacks propios. | REQUIRED A/B/C | Theme + Project |
| A11Y-007 | Targets cumplen al menos WCAG 2.2 AA (24×24 CSS px y excepciones); objetivo Hache 44×44 para acciones táctiles independientes cuando viable. | REQUIRED A/B/C | Component + Theme |
| A11Y-008 | Modales usan semántica apropiada, nombre, foco inicial razonable, confinamiento cuando modal, Escape y retorno de foco. | REQUIRED cuando aplica | Component/Extension + Project |
| A11Y-009 | Menús/disclosures/navegación móvil exponen estado, funcionan por teclado/tacto y no dependen de hover. | REQUIRED cuando aplica | Component + Project |
| A11Y-010 | `prefers-reduced-motion` reduce movimiento no esencial; no hay flashes peligrosos ni información solo animada. | REQUIRED A/B/C | Core + Theme/Extension |
| A11Y-011 | Imágenes informativas tienen alternativa; decorativas se silencian; audio/video tiene captions/transcripción/audiodescripción según contenido y WCAG aplicable. | REQUIRED cuando aplica | Project content |
| A11Y-012 | Probar zoom/reflow, lector de pantalla en CUF, teclado, contraste y errores. | REQUIRED A/B/C proporcional | Project |

El **Core** provee tokens, focus/reduced-motion y contratos. Los **componentes** proveen semántica y estados. **Theme** garantiza contraste visual. El **proyecto** responde por contenido, orden, textos alternativos, headings, idioma, multimedia y pruebas sobre pantallas reales.

## 8. Seguridad

El baseline se inspira en OWASP ASVS 5.0 y Cheat Sheet Series; no declara conformidad ASVS completa.

| ID | Regla | Severidad/aplica | Verificación/ubicación |
| --- | --- | --- | --- |
| SEC-001 | HTTPS en producción; HSTS solo después de confirmar HTTPS estable. `includeSubDomains`/preload requieren confirmar todos los subdominios. | BLOCKER B/C; REQUIRED A | Header real; Project infra, Core template. |
| SEC-002 | `X-Content-Type-Options: nosniff`, Referrer-Policy y Permissions-Policy mínimas; anti-framing con CSP `frame-ancestors` o XFO compatible. | REQUIRED A/B/C | Headers por ruta. Core template + Project. |
| SEC-003 | CSP específica del proyecto, inicialmente Report-Only cuando sea necesario, sin romper CUF; documentar excepciones (`unsafe-inline`, orígenes amplios). | REQUIRED B/C; RECOMMENDED A | Header + reporte. Project; helper Core. |
| SEC-004 | Validación en servidor por tipo, longitud, rango, formato y regla de negocio; allowlist cuando sea posible. Validación cliente es UX. | BLOCKER B/C | Tests negativos. Project/domain. |
| SEC-005 | Codificación/sanitización contextual de salida; consultas parametrizadas; ningún input forma SQL/HTML/URL/comando sin control apropiado. | BLOCKER B/C | Revisión + tests. Core primitive/Project. |
| SEC-006 | CSRF en mutaciones autenticadas por cookie; métodos seguros no mutan estado. | BLOCKER B/C | Tests token/origin según diseño. Core + Project. |
| SEC-007 | Sesiones: cookies Secure en HTTPS, HttpOnly, SameSite apropiado, scope mínimo; regenerar ID al autenticar/cambiar privilegio; expiración y logout efectivos; proxy HTTPS confiable configurado. | BLOCKER B/C | Test de login/session fixation/cookies. Core + Project. |
| SEC-008 | Autenticación y recuperación aplican rate limit, respuestas no enumerables, tokens aleatorios de un uso/expirables y hashing de contraseña moderno del runtime. MFA se evalúa por riesgo. | BLOCKER C; REQUIRED B | Tests y configuración. Extension/Project. |
| SEC-009 | Autorización en servidor, deny-by-default, por acción/recurso/contexto; ocultar UI no autoriza. | BLOCKER B/C | Matriz y tests de abuso horizontal/vertical. Core + Project. |
| SEC-010 | Rate limiting para login, recuperación, formularios, APIs y operaciones costosas/sensibles. En multiinstancia debe usar estado compartido o edge. | BLOCKER C; REQUIRED B | 429 + Retry-After y pruebas. Extension/Project. |
| SEC-011 | Uploads: allowlist de tipo/extensión, verificación de contenido/MIME, tamaño/cantidad, nombre generado, storage fuera de ejecución pública, autorización y malware/CDR si el riesgo lo exige. | BLOCKER C; REQUIRED B cuando aplica | Tests con archivos maliciosos. Extension/Project. |
| SEC-012 | Errores públicos no exponen stack, SQL, tokens, paths, claves ni PII. | BLOCKER A/B/C | Test de fallos y config production. Core + Project. |
| SEC-013 | Secretos fuera de Git/frontend/logs/build artifacts; mínimo privilegio, rotación, revocación y separación por entorno. | BLOCKER A/B/C | Secret scan + inventario. Core policy + Project. |
| SEC-014 | Dependencias con vulnerabilidad explotable crítica/alta en el contexto no pueden liberarse sin actualización, mitigación equivalente o aislamiento documentado y aprobado. | BLOCKER B/C; REQUIRED A | SCA + análisis de alcanzabilidad. Project/CI. |
| SEC-015 | Logs de seguridad registran autenticación, fallos, autorización denegada, rate limit, cambios sensibles y manipulación, sin secretos. | REQUIRED B/C | Eventos correlacionados. Core contract + Project. |
| SEC-016 | Threat model ligero por CUF de nivel C y para auth, uploads, pagos/webhooks o datos sensibles. | REQUIRED C | Documento y revisión. Project. |

## 9. Robustez y resiliencia

| ID | Regla | Severidad | Evidencia |
| --- | --- | --- | --- |
| ROB-003 | Toda llamada externa tiene timeout de conexión/operación apropiado y cancelación; no puede esperar indefinidamente. | BLOCKER C; REQUIRED B | Tests de timeout/config. |
| ROB-004 | Retry solo para fallos transitorios y operaciones seguras/idempotentes; límite, exponential backoff y jitter; respetar `Retry-After`. | BLOCKER C; REQUIRED B | Test proveedor 429/5xx/timeout. |
| ROB-005 | Operaciones no idempotentes usan clave estable, constraint/claim persistente o reconciliación antes de retry. | BLOCKER C | Repetición concurrente. |
| ROB-006 | El fallo de email/WhatsApp/analytics no revierte una mutación central confirmada salvo contrato explícito. | BLOCKER C; REQUIRED B | Test de proveedor caído. |
| ROB-007 | Un CUF define modo degradado: qué sigue funcionando, qué se bloquea y qué mensaje recibe el usuario. | REQUIRED B/C | Runbook + prueba. |
| ROB-008 | Eventos pendientes/unknown/retryable son consultables y re-procesables de forma segura; existe reconciliación para divergencias. | BLOCKER C; REQUIRED B cuando crítico | Reprocess drill. |
| ROB-009 | Límites de cola/concurrencia/recursos evitan cascadas; fallos repetidos no crean retry storm. | REQUIRED C | Load/failure test proporcional. |
| ROB-010 | DNS/storage/DB/proveedor crítico tienen dueño, dependencia documentada, impacto y procedimiento de recuperación/cambio. | REQUIRED B/C | Dependency inventory/runbook. |

## 10. Manejo de errores y HTTP

La respuesta al usuario y el registro técnico son canales separados. APIs DEBERÍAN usar un envelope estable con `code`, mensaje seguro y `request_id`.

| Código | Uso esperado | Experiencia mínima |
| --- | --- | --- |
| 400 | Solicitud malformada. | Mensaje seguro; no reintentar sin corregir. |
| 401 | Falta autenticación válida. | Solicitar login/renovación sin revelar cuentas. |
| 403 | Identidad conocida sin permiso. | Explicar imposibilidad sin filtrar recurso. |
| 404 | Recurso/ruta inexistente o deliberadamente oculto. | Página/JSON útil; sin soft 404. |
| 409 | Conflicto de estado, versión, duplicado o concurrencia. | Indicar recarga/acción segura. |
| 422 | Sintaxis válida, datos/regla inválidos. | Errores accionables por campo/regla. |
| 429 | Límite excedido. | `Retry-After` cuando sea conocido. |
| 500 | Fallo interno inesperado. | Mensaje genérico + request ID; alerta según impacto. |
| 502/503 | Dependencia/servicio no disponible. | Estado temporal, fallback/retry seguro; `Retry-After` cuando proceda. |

**ERR-001 — BLOCKER A/B/C:** producción desactiva debug público y prueba al menos un fallo 500 controlado.  
**ERR-002 — REQUIRED B/C:** exceptions se capturan en frontera apropiada, preservan causa internamente y generan un único evento correlacionado.  
**ERR-003 — REQUIRED B/C:** errores esperados de dominio no se registran como 500; conflictos y validación usan 409/422 según semántica.  
**ERR-004 — REQUIRED A/B/C:** páginas 404/500 y respuestas API no filtran información sensible y mantienen navegación/soporte útil.

## 11. Observabilidad

**OBS-001 — BLOCKER B/C; REQUIRED A con servicio dinámico**  
Logs de aplicación en formato estructurado o campos parseables con timestamp UTC ISO 8601, severity, environment, service/version, event name y request ID. Para trabajos/eventos, incluir correlation ID o business operation ID no sensible.

**OBS-002 — REQUIRED B/C**  
Propagar/generar request/correlation IDs a través de aplicación e integraciones; no aceptar ciegamente IDs externos sin límites/normalización.

**OBS-003 — REQUIRED B/C**  
Severidades consistentes: DEBUG no activo globalmente en producción; INFO eventos normales significativos; WARN degradación/retry; ERROR operación fallida; CRITICAL impacto amplio o datos/seguridad.

**OBS-004 — REQUIRED B/C**  
Eventos reconstruibles: registro solicitado/confirmado/fallido; formulario recibido/procesado; pago iniciado/confirmado/rechazado; webhook recibido/verificado/procesado/duplicado/fallido; correo solicitado/aceptado/delivered/bounced/failed; cambios de permisos/configuración.

**OBS-005 — BLOCKER C; REQUIRED B**  
Health endpoints separados conceptualmente:

- liveness: proceso responde;
- readiness: puede servir tráfico sin afirmar dependencias opcionales;
- smoke/functional: CUF mínimo o comprobación externa controlada.

No incluir secretos ni detalles de infraestructura en respuestas públicas.

**OBS-006 — REQUIRED C; RECOMMENDED B**  
Métricas de latencia, tráfico, errores y saturación; además tasas de éxito/fallo/pendientes por CUF e integración. Alertas accionables tienen umbral, ventana, dueño y runbook; no alertar por ruido sin acción.

**OBS-007 — REQUIRED B/C**  
Retención, acceso y redacción de logs definidos. No registrar passwords, tokens, cookies, cuerpos completos sensibles, CVV/tarjetas completas ni PII innecesaria.

## 12. Formularios

**FORM-001 — BLOCKER B/C:** validación servidor y autorización; cliente solo mejora UX.  
**FORM-002 — REQUIRED:** labels, instrucciones, required, tipos/autocomplete/inputmode, teclado, errores accesibles y foco lógico.  
**FORM-003 — REQUIRED:** estados idle/loading/success/error; bloqueo de doble submit en UI sin eliminar successful controls; deduplicación servidor si el efecto importa.  
**FORM-004 — REQUIRED:** conservar campos válidos tras error sin persistir secretos ni datos de pago.  
**FORM-005 — REQUIRED B/C:** CSRF según autenticación y rate limit proporcional.  
**FORM-006 — REQUIRED público:** mitigación de spam escalonada: validación/rate limit, honeypot cuando sea efectivo, reputación; CAPTCHA solo ante abuso demostrado, con accesibilidad/privacidad evaluadas.  
**FORM-007 — REQUIRED:** recopilar solo datos necesarios, explicar finalidad y enlazar privacidad donde corresponda.

El Core puede aportar markup/estados/guard; el servidor y la política de datos son responsabilidad del proyecto. CAPTCHA y proveedores anti-spam son Extensions.

## 13. Comunicaciones transaccionales

**COM-001 — BLOCKER C / REQUIRED B:** persistir canal, template/version, destinatario normalizado, business operation ID, provider message ID, estado, attempt count y timestamps, minimizando contenido sensible.  
**COM-002 — REQUIRED:** estados distinguen `requested`, `accepted/sent`, `delivered`, `delayed`, `bounced/failed`, `suppressed` cuando el proveedor los soporte. `sent` no significa leído ni necesariamente entregado al inbox.  
**COM-003 — REQUIRED:** templates versionados/revisables, escaping correcto, identidad/remitente y enlaces de entorno correctos. No loggear el cuerpo completo por defecto.  
**COM-004 — REQUIRED B/C:** retries limitados solo para fallos temporales; deduplicación/idempotency claim; hard bounce/suppression no se reintenta ciegamente.  
**COM-005 — REQUIRED C:** fallback definido cuando la comunicación es parte del CUF; no prometer canal alternativo que no esté probado.  
**COM-006 — REQUIRED:** autenticación/configuración de dominio y prueba real desde host de producción/staging. Privacidad/consentimiento según tipo de mensaje y ley aplicable.

Adaptadores de email, WhatsApp y SMS son Extensions. El contrato de estados y trazabilidad puede vivir en Core.

## 14. Webhooks

| ID | Regla | Severidad |
| --- | --- | --- |
| WH-001 | HTTPS, método/content-type/tamaño permitidos y autenticidad/firma sobre bytes raw según proveedor; comparación constante y protección de replay/timestamp cuando exista. | BLOCKER B/C |
| WH-002 | Persistir provider, event ID, type, received_at, signature result, payload hash/referencia segura, estado y attempts antes o junto al procesamiento durable. | BLOCKER C; REQUIRED B |
| WH-003 | Unique constraint/claim evita procesar duplicados; duplicado procesado responde éxito sin repetir efectos. | BLOCKER B/C |
| WH-004 | No asumir orden. Transiciones protegen estados finales y comparan versión/timestamp cuando el contrato lo permita. | BLOCKER C; REQUIRED B |
| WH-005 | Responder rápido tras validación/persistencia; trabajo lento pasa a procesamiento posterior cuando el riesgo/latencia lo requiere. | REQUIRED B/C |
| WH-006 | Reintentos del proveedor y re-proceso manual son seguros; existe dead-letter/failed state e interfaz/runbook de recuperación. | BLOCKER C; REQUIRED B cuando crítico |
| WH-007 | En pagos/estado crítico, consultar recurso autoritativo y validar referencia, monto, moneda y contexto antes de mutar. | BLOCKER C |
| WH-008 | Logs y auditoría usan IDs/hash; payload sensible tiene acceso/retención limitados. | REQUIRED B/C |

## 15. Base de datos y datos

**DB-001 — BLOCKER B/C:** migraciones versionadas, inmutables tras aplicar, probadas en staging/clon y con verificación posterior.  
**DB-002 — BLOCKER C / REQUIRED B:** integridad crítica reforzada con tipos, NOT NULL, UNIQUE, CHECK/FK/transacciones/locks según regla; no solo validación UI.  
**DB-003 — REQUIRED B/C:** índices se justifican por consultas/constraints y se verifica plan/rendimiento para tablas críticas; no indexar por intuición masiva.  
**DB-004 — BLOCKER C:** operaciones multi-escritura críticas son atómicas o tienen compensación/reconciliación explícita.  
**DB-005 — REQUIRED:** timestamps almacenan instante inequívoco (normalmente UTC) y la zona operativa IANA se aplica en dominio/presentación; no usar abreviaturas ambiguas.  
**DB-006 — BLOCKER B/C:** backups automáticos según RPO; cifrado/acceso/retención definidos; fallo de backup alerta.  
**DB-007 — BLOCKER C; REQUIRED B:** restore probado en entorno aislado, con RTO/RPO medidos y evidencia reciente proporcional al riesgo.  
**DB-008 — REQUIRED:** borrado hard/soft se decide por integridad, privacidad, auditoría y recuperación. Soft delete no es default universal ni satisface por sí solo eliminación legal.  
**DB-009 — REQUIRED C:** conciliaciones/snapshots financieros preservan evidencia histórica; correcciones no reescriben silenciosamente el pasado.

## 16. Dependencias y supply chain

**DEP-001 — REQUIRED A/B/C:** dependencias directas/transitivas declaradas; lockfile versionado cuando el ecosistema lo soporte; builds reproducibles.  
**DEP-002 — REQUIRED:** minimizar paquetes; justificar dependencia nueva por valor, mantenimiento, licencia y superficie.  
**DEP-003 — BLOCKER B/C:** SCA en CI o release; triage por severidad, alcanzabilidad, exposición y fix; SLA definido por nivel.  
**DEP-004 — REQUIRED:** paquetes abandonados/críticos tienen plan de reemplazo, aislamiento o ownership; no actualizar majors automáticamente sin pruebas.  
**DEP-005 — REQUIRED cuando distribuye:** licencias compatibles y avisos requeridos.  
**DEP-006 — RECOMMENDED C:** fijar acciones/containers por versión/digest y revisar provenance/SBOM cuando el riesgo lo justifique.

## 17. Configuración, secretos y privacidad

**CFG-001 — BLOCKER:** development, test/staging y production usan configuración, datos y credenciales separados.  
**CFG-002 — BLOCKER:** config de dominio/URLs, DB, proveedores, timeouts, feature flags y secretos externos al código; `.env.example` solo nombres/valores ficticios.  
**CFG-003 — BLOCKER:** secretos no llegan al frontend, Git, logs, errores, backups sin protección ni artifacts. Rotación/revocación probadas para secretos críticos.  
**CFG-004 — REQUIRED:** startup valida configuración obligatoria y falla sin imprimir valores; cambios de configuración son auditables y reversibles.  
**PRIV-001 — REQUIRED cuando hay datos personales:** inventario de datos/finalidad/base/terceros/retención/acceso y canal de derechos según jurisdicción.  
**PRIV-002 — REQUIRED:** minimización por campo, acceso mínimo, cifrado en tránsito y en reposo cuando riesgo/ley lo requiera, y eliminación/anonimización controlada.  
**PRIV-003 — REQUIRED:** analytics/cookies/trackers declarados y configurados según consentimiento/ley aplicable; no asumir una regla legal universal desde Core.

## 18. Deployment y rollback

**DPL-001 — BLOCKER A/B/C:** desplegar artefacto/commit exacto que pasó CI; build separado de release/run; no construir cambios no revisados directamente en producción.  
**DPL-002 — BLOCKER:** preflight valida runtime, configuración, espacio/permisos, backup/restore readiness, conectividad crítica y compatibilidad de versión.  
**DPL-003 — BLOCKER B/C:** migraciones tienen estrategia expand/contract o compatibilidad código-esquema; se identifica el punto después del cual rollback de código no es seguro.  
**DPL-004 — REQUIRED:** despliegue registra estado `started`, `code_changed`, `migrations_applied`, `tests_passed`, `healthy`, `failed`, `rolled_back/manual_recovery`; un script terminado no equivale a servicio sano.  
**DPL-005 — BLOCKER:** health + smoke de CUF aplicable después del release; observar ventana mínima definida antes de cerrar.  
**DPL-006 — BLOCKER:** rollback documentado por código, DB, assets y configuración; target exacto y criterios de activación; ensayo en staging.  
**DPL-007 — REQUIRED C:** evitar cambios irreversibles en el mismo release que elimina compatibilidad; usar deploys incrementales/canary/blue-green si el riesgo lo justifica, no por moda.  
**DPL-008 — REQUIRED:** fallo parcial deja estado visible, alerta y runbook; no se continúa silenciosamente.  
**DPL-009 — REQUIRED:** permisos mínimos de archivos/proceso, secrets protegidos, caches calentadas/invalidadas conscientemente.

Rollback se activa ante: health/smoke fallido, error rate/CUF degradado sobre umbral, corrupción/incompatibilidad o exposición de seguridad. Si rollback empeora integridad, se detiene tráfico/mutaciones y se ejecuta recuperación explícita.

## 19. Testing

La estrategia es proporcional; no se exige 100% de cobertura.

| Tipo | A | B | C | Objetivo |
| --- | --- | --- | --- | --- |
| Unit | Según lógica | Required en reglas | Required | Reglas, estados, validadores. |
| Integration | Según integración | Required | Required | DB, auth, proveedores/adaptadores. |
| E2E | CUF principal | CUF | CUF críticos y fallos | Recorrido desplegado. |
| Smoke | Páginas clave | CUF mínimo | CUF + dependencias | Release real. |
| Regression | Hallazgos relevantes | Required | Required | Evitar recurrencia. |
| Security sanity | Headers/secret scan | Auth/CSRF/authz/rate | + webhooks/uploads/concurrencia | Baseline de abuso. |
| Accessibility | Auto + manual | Auto + manual CUF | Auto + manual CUF | WCAG/uso real. |
| SEO | Público | Público/híbrido | Público/híbrido | Norma SEO separada. |
| Performance | Páginas | CUF | CUF y carga/fallo proporcional | Budgets/CWV. |

**TEST-001 — BLOCKER:** cada CUF tiene al menos happy path automatizado o una justificación técnica con smoke manual reproducible; B/C incluye fallos críticos.  
**TEST-002 — BLOCKER C:** probar duplicados, concurrencia, timeout, retry, evento fuera de orden, mismatch y dependencia caída.  
**TEST-003 — REQUIRED:** fixtures aislados; ninguna prueba muta producción.  
**TEST-004 — REQUIRED:** CI falla ante test obligatorio; flaky tests se reparan/aislan con dueño y plazo, no se ignoran indefinidamente.  
**TEST-005 — REQUIRED:** pruebas manuales indispensables tienen pasos, fecha, entorno, evidencia y responsable.

## 20. SEO y compatibilidad con normas existentes

- Sitios públicos/híbridos DEBEN cumplir el módulo SEO de Hache Base.
- Apps privadas DEBEN declarar el modo de no indexación correspondiente.
- Este estándar solo añade la condición de release: sitemap/robots/canonical/status/enlaces y smoke SEO deben corresponder al artefacto desplegado.
- Accesibilidad, responsive, Theme, imágenes y CWV se rigen en detalle por `DESIGN-SYSTEM-2026-FINAL.md`; aquí se exige su evidencia de producción.
- Si dos normas difieren, se registra conflicto; no se resuelve silenciosamente. Para seguridad, privacidad o integridad prevalece el control más protector hasta decisión humana.

## 21. Definition of Done — PRODUCTION READY

Un proyecto es **Production Ready** únicamente si:

1. nivel de riesgo y CUF están aprobados;
2. todos los BLOCKER y REQUIRED aplicables están cumplidos con evidencia vigente;
3. CI y pruebas requeridas pasan sobre el commit/artefacto exacto;
4. no hay secretos versionados ni vulnerabilidades explotables sin resolver según SEC-014;
5. errores, logs, health, alertas y runbooks permiten detectar y reconstruir fallos proporcionales al nivel;
6. backup/rollback existen y restore está probado cuando aplica;
7. migraciones y compatibilidad código-datos fueron probadas;
8. integraciones distinguen aceptación de confirmación y gestionan duplicados/fallos;
9. accesibilidad, performance y SEO aplicable tienen evidencia real o laboratorio representativo;
10. deploy y smoke de producción tienen responsable, ventana y criterio de rollback;
11. deuda RECOMMENDED queda registrada con dueño y prioridad;
12. aprobación final identifica fecha, commit, entorno, evaluador y evidencia.

No son evidencia suficiente: “funciona en mi máquina”, “el pipeline terminó”, “el proveedor devolvió 200”, “el deploy dijo OK”, “hay backup” sin restore, o “Lighthouse dio 100” sin revisar CUF/campo.

## 22. Automation Opportunities

Controles candidatos para una fase posterior, sin imponer una herramienta concreta:

- CI: sintaxis, tests, schemas/migraciones, idempotencia, licencias, dependency/SCA, secret scan y lockfiles.
- HTTP smoke: status, redirects, headers, CSP Report-Only, cookies, cache, compresión, 404/500 y health.
- Lighthouse/axe u equivalentes con páginas/CUF y budgets versionados.
- SEO: robots, sitemap, canonical, schema, indexabilidad, links rotos y status.
- Assets: peso, dimensiones, formatos, `srcset`, lazy/LCP, fuentes y terceros.
- Webhooks/jobs: fixtures repetidos/fuera de orden, firma inválida, replay y reprocess.
- Deploy: commit exacto, backup checksum, estado por fase, health/smoke y rollback drill.
- Observabilidad: schema de logs, request ID, alertas sintéticas y eventos CUF.
- Infra: expiración TLS/DNS, backup freshness, capacidad de disco y dependencias externas.

La automatización no reemplaza revisión humana de accesibilidad, privacidad, threat model, contenido, UX, restore ni decisiones de riesgo.

## 23. Revisión de la norma

Revisar al menos anualmente o ante cambios materiales en WCAG, Core Web Vitals, OWASP ASVS, stack, proveedores o incidentes. Cada revisión registra versión, fuentes, cambios y migración requerida. El Core permanece pequeño: primero contrato y evidencia; runtime especializado solo como Extension con casos reales.

## 24. Registro canónico de controles

### 24.1 Convenciones

- **Aplica A** significa A, B y C; **B** significa B y C; **C** significa solo C.
- Una condición explícita restringe el control aun dentro del nivel indicado.
- En severidad mixta, por ejemplo `REQUIRED B; BLOCKER C`, el mismo control es REQUIRED para B y BLOCKER para C.
- **Automatizable:** `Sí`, `Parcial` o `No`. No autoriza implementación en esta misión.
- **Humana:** indica si el resultado final exige juicio o comprobación humana aunque exista automatización.

### 24.2 Gobierno, alcance y CUF

| ID | Regla verificable | Severidad | Aplica | Evidencia mínima | Automatizable | Humana |
| --- | --- | --- | --- | --- | --- | --- |
| GOV-001 | Declarar y justificar nivel A/B/C; elevar el módulo/ruta que reúna condiciones de mayor riesgo. | BLOCKER | A | Perfil aprobado con criterios de nivel. | Parcial | Sí |
| GOV-002 | Inventariar URLs/servicios, datos, secretos, dependencias, integraciones y CUF con dueños. | REQUIRED | A | Inventario versionado y responsables. | Parcial | Sí |
| GOV-003 | Cada CUF documenta precondición, pasos, resultado, mutaciones, fallos, idempotencia cuando aplica, pruebas, smoke y señales. | REQUIRED | A | Matriz CUF enlazada a tests/telemetría/runbook. | Parcial | Sí |
| GOV-004 | Usar N/A solo por no aplicabilidad demostrada; NOT EVALUATED nunca equivale a PASS. | BLOCKER | A | Justificación y evidencia por cada N/A; estados de evaluación. | Parcial | Sí |

### 24.3 Performance

| ID | Regla verificable | Severidad | Aplica | Evidencia mínima | Automatizable | Humana |
| --- | --- | --- | --- | --- | --- | --- |
| PERF-001 | Cumplir LCP ≤2.5 s, INP ≤200 ms y CLS ≤0.1 en p75, móvil y desktop, cuando exista campo suficiente. | REQUIRED | A, cuando hay datos de campo suficientes | CrUX/RUM por plantilla/CUF y ventana documentada. | Sí | Sí |
| PERF-002 | Sin campo suficiente, medir build de producción en laboratorio móvil/red/CPU representativos y registrar causas. | REQUIRED | A | Reporte versionado de Lighthouse o equivalente. | Sí | Sí |
| PERF-003 | No usar score Lighthouse como sustituto de campo; investigar regresión material contra baseline. | REQUIRED | A | Comparación y resolución/aceptación documentada. | Parcial | Sí |
| PERF-004 | Definir presupuesto justificado para JS, CSS, imágenes, fuentes y terceros. | REQUIRED | A | Presupuesto aprobado y CI cuando sea estable. | Sí | Sí |
| PERF-005 | Imágenes con dimensiones/aspect ratio, responsive cuando corresponde y formatos modernos cuando aportan beneficio. | REQUIRED | A, cuando hay imágenes | Markup, network y comparación de peso/calidad. | Sí | Sí |
| PERF-006 | No diferir el recurso LCP si retrasa su descubrimiento; diferir recursos fuera de viewport cuando sea seguro. | REQUIRED | A, cuando hay recursos diferibles | Waterfall y elemento LCP identificado. | Parcial | Sí |
| PERF-007 | Usar preload solo para recursos críticos consumidos pronto y con tipo/CORS correctos. | REQUIRED | A, cuando hay preload | Network sin preloads ociosos/duplicados. | Sí | Sí |
| PERF-008 | Limitar variantes de fuentes, usar formato/display/fallback adecuados y evitar shifts materiales. | REQUIRED | A, cuando hay webfonts | Network, CSS y CLS. | Parcial | Sí |
| PERF-009 | Reducir/diferir JS/CSS no usado, render-blocking y tareas largas; decoración no bloquea CUF. | REQUIRED | A | Coverage, waterfall y long tasks. | Parcial | Sí |
| PERF-010 | Cada tercero tiene dueño, propósito, datos, coste, timeout/fallback y criterio de retiro. | REQUIRED | A, cuando hay terceros | Inventario y medición con/sin tercero. | Parcial | Sí |
| PERF-011 | Configurar compresión y caché explícita por HTML, assets, API y datos privados; probar invalidación. | REQUIRED | A | Headers reales y prueba de invalidación/no-store. | Sí | Sí |
| PERF-012 | Probar además en dispositivo móvil representativo con red/CPU limitadas. | RECOMMENDED | A | Perfil y resultados registrados. | Parcial | Sí |

### 24.4 Accesibilidad

| ID | Regla verificable | Severidad | Aplica | Evidencia mínima | Automatizable | Humana |
| --- | --- | --- | --- | --- | --- | --- |
| A11Y-001 | Definir idioma, título, landmarks, headings y orden DOM lógico. | REQUIRED | A | Inspección de páginas/plantillas reales. | Parcial | Sí |
| A11Y-002 | Operar todas las acciones/CUF por teclado, sin traps y con orden lógico. | REQUIRED A; BLOCKER B/C | A | Prueba manual de teclado sobre CUF. | Parcial | Sí |
| A11Y-003 | Foco perceptible y no totalmente oculto por sticky/overlays. | REQUIRED | A | Prueba visual/teclado en viewports reales. | Parcial | Sí |
| A11Y-004 | Controles con nombre accesible, labels visibles y ARIA solo cuando es necesaria y veraz. | REQUIRED A; BLOCKER B/C | A, cuando hay controles/formularios | Accessibility tree + revisión de markup. | Parcial | Sí |
| A11Y-005 | Errores identifican campo, causa y corrección; no dependen solo de color. | REQUIRED | B, cuando hay formularios | Pruebas de error con teclado/lector. | Parcial | Sí |
| A11Y-006 | Contraste WCAG 2.2 AA en cada Theme y estado habilitado. | REQUIRED | A | Medición automática + revisión visual. | Parcial | Sí |
| A11Y-007 | Targets cumplen WCAG 2.2 AA; objetivo Hache 44×44 cuando sea viable. | REQUIRED | A, cuando hay acciones | Medición CSS/viewport y excepciones justificadas. | Sí | Sí |
| A11Y-008 | Modales gestionan semántica, nombre, foco, modalidad, Escape y retorno. | REQUIRED | A, cuando hay modales | Test teclado/lector y estado de fondo. | Parcial | Sí |
| A11Y-009 | Menús/disclosures/navegación móvil exponen estado y funcionan con teclado/tacto sin hover obligatorio. | REQUIRED | A, cuando existen | Test de interacción en móvil/teclado. | Parcial | Sí |
| A11Y-010 | Reduced motion, ausencia de flashes peligrosos e información no dependiente del movimiento. | REQUIRED | A, cuando hay movimiento | Preferencia reduce + revisión visual. | Parcial | Sí |
| A11Y-011 | Alternativas de imágenes y captions/transcripción/audiodescripción cuando WCAG/contenido lo exige. | REQUIRED | A, cuando hay contenido no textual/multimedia | Revisión de contenido y reproducción. | Parcial | Sí |
| A11Y-012 | Probar zoom/reflow, teclado, contraste, errores y lector de pantalla proporcional a los CUF. | REQUIRED | A | Evidencia manual + reporte automatizado complementario. | Parcial | Sí |

### 24.5 Seguridad

| ID | Regla verificable | Severidad | Aplica | Evidencia mínima | Automatizable | Humana |
| --- | --- | --- | --- | --- | --- | --- |
| SEC-001 | HTTPS; HSTS solo tras estabilidad; `includeSubDomains`/preload solo tras verificar todos los subdominios. | REQUIRED A; BLOCKER B/C | A | TLS/headers reales e inventario de subdominios. | Sí | Sí |
| SEC-002 | Aplicar nosniff, Referrer-Policy, Permissions-Policy y anti-framing apropiados. | REQUIRED | A | Headers por rutas representativas. | Sí | Sí |
| SEC-003 | CSP específica, probada y desplegada de forma segura; documentar excepciones. | RECOMMENDED A; REQUIRED B/C | A | Header/report-only, reportes y prueba CUF. | Parcial | Sí |
| SEC-004 | Validar entrada en servidor por tipo, longitud, rango, formato y negocio. | BLOCKER | B | Tests negativos por endpoint/CUF. | Sí | Sí |
| SEC-005 | Codificar/sanitizar salida por contexto y parametrizar SQL/comandos/rutas. | BLOCKER | B | Revisión de sinks + tests de inyección. | Parcial | Sí |
| SEC-006 | Proteger CSRF en mutaciones autenticadas por cookie; métodos seguros no mutan. | BLOCKER | B, cuando hay auth por cookie/mutaciones | Tests CSRF y verificación de métodos. | Sí | Sí |
| SEC-007 | Cookies/sesiones seguras; regeneración al autenticar/elevar; expiración/logout; proxy confiable. | BLOCKER | B, cuando hay sesiones | Tests de cookies, fixation, logout y proxy. | Parcial | Sí |
| SEC-008 | Auth/recuperación con rate limit, no enumeración práctica, tokens seguros y password hashing; evaluar MFA. | REQUIRED B; BLOCKER C | B, cuando hay autenticación | Tests de abuso/recuperación y configuración. | Parcial | Sí |
| SEC-009 | Autorizar en servidor deny-by-default por acción/recurso/contexto. | BLOCKER | B, cuando hay recursos protegidos | Matriz y tests horizontales/verticales. | Sí | Sí |
| SEC-010 | Rate limit en rutas sensibles/costosas; estado compartido en multiinstancia. | REQUIRED B; BLOCKER C | B, cuando hay rutas expuestas/sensibles | Tests 429/Retry-After y arquitectura de storage. | Sí | Sí |
| SEC-011 | Uploads con allowlist, contenido/MIME, límites, nombre/storage seguro, auth y controles extra según riesgo. | REQUIRED B; BLOCKER C | B, cuando hay uploads | Corpus de archivos maliciosos y revisión storage. | Parcial | Sí |
| SEC-012 | No exponer stack, SQL, tokens, paths, claves ni PII en errores públicos. | BLOCKER | A | Tests de fallos y config de producción. | Sí | Sí |
| SEC-013 | Secretos fuera de Git/frontend/logs/artifacts; mínimo privilegio, rotación, revocación y separación por entorno. | BLOCKER | A | Secret scan, inventario y drill de rotación crítico. | Parcial | Sí |
| SEC-014 | No liberar vulnerabilidad explotable crítica/alta sin fix, mitigación equivalente o aislamiento aprobado. | REQUIRED A; BLOCKER B/C | A, cuando hay dependencias | SCA + triage de alcanzabilidad/exposición. | Sí | Sí |
| SEC-015 | Registrar eventos de auth, denegación, rate limit, cambios sensibles y manipulación, sin secretos. | REQUIRED | B, cuando existen esos eventos | Catálogo y muestras de logs/auditoría. | Parcial | Sí |
| SEC-016 | Threat model ligero para CUF C y auth/uploads/pagos/webhooks/datos sensibles. | REQUIRED | C | Documento revisado con mitigaciones. | No | Sí |

### 24.6 Robustez y resiliencia

| ID | Regla verificable | Severidad | Aplica | Evidencia mínima | Automatizable | Humana |
| --- | --- | --- | --- | --- | --- | --- |
| ROB-001 | Modelar `INITIATED`, `PROCESSING`, `CONFIRMED`, `FAILED`, `RETRYABLE`, `CANCELLED` y `UNKNOWN` o equivalentes, con transiciones. | BLOCKER | B, cuando hay operación externa asíncrona con efecto relevante | Diagrama/tabla de estados + tests de transición. | Parcial | Sí |
| ROB-002 | Interpretar `2xx` según contrato; aceptación no equivale a entrega/pago/completado. | REQUIRED B; BLOCKER C | B, cuando el proveedor confirma en fase posterior | Tests ACK vs confirmación y evidencia autoritativa. | Sí | Sí |
| ROB-003 | Toda llamada externa tiene timeouts finitos de conexión/operación y cancelación. | REQUIRED B; BLOCKER C | B, cuando hay llamadas externas | Config + tests de timeout. | Sí | Sí |
| ROB-004 | Retry solo temporal/seguro, limitado, con backoff+jitter y `Retry-After`. | REQUIRED B; BLOCKER C | B, cuando existe retry | Tests 429/5xx/timeout e idempotencia. | Sí | Sí |
| ROB-005 | Operación no idempotente usa clave estable, constraint/claim o reconciliación antes de retry. | BLOCKER | C | Tests repetidos y concurrentes. | Sí | Sí |
| ROB-006 | Fallo de notificación/analytics no revierte mutación central confirmada salvo contrato explícito. | REQUIRED B; BLOCKER C | B, cuando hay efectos secundarios | Test de proveedor caído después de commit central. | Sí | Sí |
| ROB-007 | Cada CUF define modo degradado, bloqueos y mensaje al usuario. | REQUIRED | B | Runbook y prueba de dependencia caída. | Parcial | Sí |
| ROB-008 | Pendientes/unknown/retryable son consultables, reprocesables con seguridad y reconciliables. | REQUIRED B; BLOCKER C | B, cuando existen estados pendientes/retryables | Reprocess/reconciliation drill. | Parcial | Sí |
| ROB-009 | Límites de cola/concurrencia/retry evitan cascadas y retry storms. | REQUIRED | C, cuando hay procesamiento concurrente/cola | Load/failure test proporcional. | Parcial | Sí |
| ROB-010 | Dependencias críticas tienen dueño, impacto y recuperación/cambio documentado. | REQUIRED | B | Inventario y runbook probado proporcionalmente. | Parcial | Sí |

### 24.7 Errores y observabilidad

| ID | Regla verificable | Severidad | Aplica | Evidencia mínima | Automatizable | Humana |
| --- | --- | --- | --- | --- | --- | --- |
| ERR-001 | Desactivar debug público y probar un 500 controlado sin filtración. | BLOCKER | A | Request/response de prueba y config. | Sí | Sí |
| ERR-002 | Capturar exceptions en frontera, preservar causa internamente y emitir un evento correlacionado. | REQUIRED | B, cuando hay runtime dinámico | Test de excepción + log correlacionado. | Sí | Sí |
| ERR-003 | Usar 409/422 para conflicto/validación y no tratar errores de dominio como 500. | REQUIRED | B, cuando hay API/mutaciones | Tests de status y códigos internos. | Sí | Sí |
| ERR-004 | 404/500 y errores API son seguros y ofrecen navegación/instrucción útil. | REQUIRED | A | Pruebas de rutas/errores reales. | Sí | Sí |
| OBS-001 | Logs estructurados/parseables con UTC, severity, environment, version, event y request ID. | REQUIRED A cuando dinámico; BLOCKER B/C | A, cuando hay runtime dinámico | Muestras y validación de schema. | Sí | Sí |
| OBS-002 | Generar/propagar request/correlation IDs y normalizar IDs externos. | REQUIRED | B, cuando hay más de una frontera/proceso | Tests request→job/webhook/proveedor. | Sí | Sí |
| OBS-003 | Severidades consistentes; DEBUG no global en producción. | REQUIRED | B, cuando hay logs de aplicación | Config y muestras por severidad. | Sí | Sí |
| OBS-004 | Eventos permiten reconstruir CUF e integraciones críticas. | REQUIRED | B | Timeline reconstruido desde evidencia. | Parcial | Sí |
| OBS-005 | Distinguir liveness/readiness/smoke sin filtrar secretos. | REQUIRED B; BLOCKER C | B, cuando hay servicio dinámico | Endpoints/checks y pruebas de fallo. | Sí | Sí |
| OBS-006 | Medir golden signals y CUF; alertas con umbral, ventana, dueño y runbook. | RECOMMENDED B; REQUIRED C | B, cuando hay servicio operado | Dashboard/alert tests/runbook. | Parcial | Sí |
| OBS-007 | Definir acceso/retención/redacción; no loggear secretos ni datos sensibles innecesarios. | REQUIRED | B, cuando hay logs | Política, muestras y test de redacción. | Parcial | Sí |

### 24.8 Formularios y comunicaciones

| ID | Regla verificable | Severidad | Aplica | Evidencia mínima | Automatizable | Humana |
| --- | --- | --- | --- | --- | --- | --- |
| FORM-001 | Validar y autorizar en servidor; validación cliente es UX. | BLOCKER | B, cuando hay formularios con efecto | Tests negativos servidor. | Sí | Sí |
| FORM-002 | Labels/instrucciones/required/tipos/autocomplete/inputmode/errores/foco accesibles. | REQUIRED | B, cuando hay formularios | Test markup, teclado y lector. | Parcial | Sí |
| FORM-003 | Estados idle/loading/success/error; doble submit UI y dedupe servidor si el efecto importa. | REQUIRED | B, cuando hay formularios | Tests UI + requests repetidos. | Sí | Sí |
| FORM-004 | Conservar datos válidos tras error sin persistir secretos/pagos. | REQUIRED | B, cuando hay formularios | Test de error y revisión storage. | Parcial | Sí |
| FORM-005 | CSRF según auth y rate limit proporcional. | REQUIRED | B, cuando el formulario muta/está expuesto | Tests CSRF/rate limit. | Sí | Sí |
| FORM-006 | Mitigación spam escalonada; CAPTCHA solo con abuso justificado y evaluación a11y/privacidad. | REQUIRED | B, cuando hay formulario público | Evidencia de controles/abuso y revisión humana. | Parcial | Sí |
| FORM-007 | Recopilar solo datos necesarios y explicar finalidad/privacidad. | REQUIRED | B, cuando se recopilan datos | Inventario por campo y UI/política. | Parcial | Sí |
| COM-001 | Persistir canal, template/version, destinatario normalizado, operation/provider ID, estado, attempts y timestamps. | REQUIRED B; BLOCKER C | B, cuando hay comunicación transaccional | Registro persistente y consultas. | Parcial | Sí |
| COM-002 | Distinguir requested, accepted/sent, delivered, delayed, bounced/failed y suppressed según proveedor. | REQUIRED | B, cuando proveedor ofrece esos eventos | State mapping + fixtures/webhooks. | Sí | Sí |
| COM-003 | Templates versionados, escape correcto, remitente/enlaces correctos y sin body sensible en logs por defecto. | REQUIRED | B, cuando hay comunicación transaccional | Template/version review y muestras. | Parcial | Sí |
| COM-004 | Retry temporal limitado, dedupe/claim y no reintentar hard bounce/suppression ciegamente. | REQUIRED | B, cuando hay retry/eventos de entrega | Tests de retry/dedupe/bounce. | Sí | Sí |
| COM-005 | Fallback crítico definido y probado, sin promesas documentales falsas. | REQUIRED | C, cuando la comunicación es parte del CUF | Failure drill del canal/fallback. | Parcial | Sí |
| COM-006 | Verificar identidad/DNS/remitente y prueba real desde host objetivo; privacidad/consentimiento aplicables. | REQUIRED | B, cuando hay comunicación | DNS/provider evidence + prueba controlada. | Parcial | Sí |

### 24.9 Webhooks y base de datos

| ID | Regla verificable | Severidad | Aplica | Evidencia mínima | Automatizable | Humana |
| --- | --- | --- | --- | --- | --- | --- |
| WH-001 | HTTPS, método/content-type/tamaño y firma sobre raw body; replay/timestamp cuando exista. | BLOCKER | B, cuando hay webhooks | Tests firma/replay/request inválido. | Sí | Sí |
| WH-002 | Persistir provider/event ID/type/received/signature/payload hash o referencia/estado/attempts. | REQUIRED B; BLOCKER C | B, cuando hay webhooks con efecto | Ledger/event record y constraints. | Sí | Sí |
| WH-003 | Unique/claim evita duplicados; duplicado procesado responde éxito sin repetir efectos. | BLOCKER | B, cuando hay webhooks | Tests duplicados/concurrentes. | Sí | Sí |
| WH-004 | No asumir orden; proteger estados finales y comparar versión/timestamp cuando el contrato lo permite. | REQUIRED B; BLOCKER C | B, cuando eventos pueden llegar fuera de orden | Tests de permutaciones/tardíos. | Sí | Sí |
| WH-005 | Responder rápido tras validación/persistencia y desacoplar trabajo lento cuando corresponde. | REQUIRED | B, cuando hay webhooks | Test de latencia y durable handoff. | Sí | Sí |
| WH-006 | Reintento y re-proceso son seguros; estado failed/dead-letter equivalente y runbook. | REQUIRED B; BLOCKER C | B, cuando webhook es reintentable/crítico | Reprocess drill y evidencia de fallo. | Parcial | Sí |
| WH-007 | En pagos/estado crítico consultar fuente autoritativa y validar referencia, monto, moneda y contexto. | BLOCKER | C, cuando webhook cambia pago/estado crítico | Fixtures/provider sandbox y mismatch tests. | Sí | Sí |
| WH-008 | Logs usan IDs/hash; payload sensible tiene acceso/retención limitados. | REQUIRED | B, cuando hay webhooks | Política, muestra de logs/storage. | Parcial | Sí |
| DB-001 | Migraciones versionadas/inmutables, probadas fuera de producción y verificadas después. | BLOCKER | B, cuando hay DB/esquema mutable | Historial, staging run y checks. | Sí | Sí |
| DB-002 | Reforzar integridad crítica con tipos/NOT NULL/UNIQUE/CHECK/FK/transacciones/locks según regla. | REQUIRED B; BLOCKER C | B, cuando hay DB | Schema review + tests de violación/concurrencia. | Sí | Sí |
| DB-003 | Justificar índices por consultas/constraints y verificar rutas críticas. | REQUIRED | B, cuando hay DB con volumen/consultas relevantes | EXPLAIN/medición y schema. | Parcial | Sí |
| DB-004 | Multi-escritura crítica es atómica o tiene compensación/reconciliación. | BLOCKER | C, cuando hay multi-escritura crítica | Tests de fallo parcial/transacción. | Sí | Sí |
| DB-005 | Timestamps inequívocos y zona IANA aplicada en dominio/presentación. | REQUIRED | B, cuando hay fechas persistidas/reglas temporales | Schema/config y tests de frontera. | Sí | Sí |
| DB-006 | Backups automáticos según RPO, protegidos, retenidos y con alerta de fallo. | BLOCKER | B, cuando hay datos persistentes no reproducibles | Jobs, backup freshness, permisos/cifrado/alerta. | Parcial | Sí |
| DB-007 | Restore probado aisladamente con RTO/RPO medidos y evidencia vigente. | REQUIRED B; BLOCKER C | B, cuando aplica DB-006 | Restore drill y reporte. | Parcial | Sí |
| DB-008 | Justificar hard/soft delete por integridad, privacidad, auditoría y recuperación. | REQUIRED | B, cuando hay borrado/retención | Política y tests de referencias. | Parcial | Sí |
| DB-009 | Preservar evidencia financiera/histórica; no reescribir/eliminar silenciosamente. | REQUIRED | C, cuando hay snapshots/evidencia crítica | Audit trail y tests de corrección. | Parcial | Sí |

### 24.10 Dependencias, configuración y privacidad

| ID | Regla verificable | Severidad | Aplica | Evidencia mínima | Automatizable | Humana |
| --- | --- | --- | --- | --- | --- | --- |
| DEP-001 | Declarar dependencias directas/transitivas, versionar lockfile si existe y lograr build reproducible. | REQUIRED | A, cuando hay dependencias/build | Manifests/lockfile y clean build. | Sí | Sí |
| DEP-002 | Minimizar/justificar dependencia por valor, mantenimiento, licencia y superficie. | REQUIRED | A, cuando se añade/retiene dependencia | Registro de decisión/inventario. | Parcial | Sí |
| DEP-003 | Ejecutar SCA y triage por severidad, alcanzabilidad, exposición y SLA. | BLOCKER | B, cuando hay dependencias | Reporte SCA y decisiones. | Sí | Sí |
| DEP-004 | Paquete abandonado/crítico tiene reemplazo, aislamiento o dueño; majors no se actualizan sin pruebas. | REQUIRED | A, cuando existe el caso | Health review y plan. | Parcial | Sí |
| DEP-005 | Licencias compatibles y avisos presentes cuando se distribuye. | REQUIRED | A, cuando hay terceros/licencias | Scan/revisión de licencias. | Sí | Sí |
| DEP-006 | Pin/provenance/SBOM cuando el riesgo lo justifica. | RECOMMENDED | C | SBOM y configuración CI. | Sí | Sí |
| CFG-001 | Separar development, test/staging y production en configuración, datos y credenciales. | BLOCKER | A, cuando existen varios entornos/runtime | Matriz y pruebas de aislamiento. | Parcial | Sí |
| CFG-002 | Externalizar URLs, DB, proveedores, timeouts, flags y secretos; ejemplos solo ficticios. | BLOCKER | A, cuando existe configuración | Config interface + secret scan. | Sí | Sí |
| CFG-003 | Secretos fuera de frontend/Git/logs/artifacts/backups sin protección; rotación/revocación en críticos. | BLOCKER | A, cuando hay secretos | Scan, controles de backup y drill. | Parcial | Sí |
| CFG-004 | Startup valida config sin imprimir valores; cambios son auditables y reversibles. | REQUIRED | B, cuando hay runtime/configuración mutable | Tests de startup y audit/rollback de config. | Sí | Sí |
| PRIV-001 | Inventariar datos personales, finalidad, base, terceros, retención, acceso y canal de derechos según jurisdicción. | REQUIRED | B, cuando hay datos personales | Registro y política aprobada. | Parcial | Sí |
| PRIV-002 | Minimizar por campo y aplicar controles de acceso/cifrado/eliminación/anonimización según riesgo/ley. | REQUIRED | B, cuando hay datos personales | Field inventory, access tests y retention process. | Parcial | Sí |
| PRIV-003 | Inventariar/configurar analytics, cookies y trackers según consentimiento/ley. | REQUIRED | A, cuando existen | Scan/inventario y comportamiento de consentimiento. | Parcial | Sí |

### 24.11 Deployment, testing y SEO

| ID | Regla verificable | Severidad | Aplica | Evidencia mínima | Automatizable | Humana |
| --- | --- | --- | --- | --- | --- | --- |
| DPL-001 | Desplegar artefacto/commit exacto aprobado; separar build de release/run. | BLOCKER | A | Provenance/commit y CI aprobado. | Sí | Sí |
| DPL-002 | Preflight valida runtime, config, espacio/permisos, backup readiness, conectividad y compatibilidad aplicables. | BLOCKER | A | Salida preflight y revisión por nivel; DB checks N/A en A sin DB. | Sí | Sí |
| DPL-003 | Migraciones usan compatibilidad/expand-contract y declaran punto de no retorno. | BLOCKER | B, cuando hay migraciones | Plan por release y staging test. | Parcial | Sí |
| DPL-004 | Registrar fases aplicables: started, code/assets changed, migrations, tests, healthy, failed y rollback/recovery. | REQUIRED | A | Log/registro de deploy; fases inexistentes justificadas N/A. | Sí | Sí |
| DPL-005 | Health y smoke aplicables pasan tras release y existe ventana de observación definida. | BLOCKER | A | Resultados, versión/URL y ventana. | Sí | Sí |
| DPL-006 | Rollback documentado/probado para código/assets y, cuando existan, DB/config; target y criterios exactos. | BLOCKER | A | Drill/runbook por componentes aplicables. | Parcial | Sí |
| DPL-007 | Evitar irreversibilidad incompatible; usar estrategia gradual solo si el riesgo la justifica. | REQUIRED | C | Plan de compatibilidad/release. | Parcial | Sí |
| DPL-008 | Fallo parcial deja estado visible, alerta y runbook; no continúa silenciosamente. | REQUIRED | A | Failure drill y salida/alerta. | Parcial | Sí |
| DPL-009 | Permisos mínimos y caches calentadas/invalidadas conscientemente. | REQUIRED | A, según stack | Revisión de permisos/cache. | Parcial | Sí |
| TEST-001 | Cada CUF tiene happy path automatizado o smoke manual reproducible; B/C cubre fallos críticos. | BLOCKER | A | Mapa CUF→tests/evidencia. | Parcial | Sí |
| TEST-002 | Probar duplicados, concurrencia, timeout, retry, fuera de orden, mismatch y dependencia caída. | BLOCKER | C, para CUF/integraciones correspondientes | Suite y resultados. | Sí | Sí |
| TEST-003 | Fixtures aislados; ninguna prueba muta producción. | REQUIRED | A, cuando hay pruebas con datos/mutación | Config y evidencia de entorno. | Sí | Sí |
| TEST-004 | CI bloquea fallos obligatorios; flaky tests tienen dueño/plazo. | REQUIRED | A, cuando hay CI/tests | Branch rules/CI y registro flaky. | Sí | Sí |
| TEST-005 | Pruebas manuales registran pasos, fecha, entorno, evidencia y responsable. | REQUIRED | A, cuando existe prueba manual requerida | Acta/reporte enlazado. | Parcial | Sí |
| SEO-001 | Cumplir módulo SEO vigente en público/híbrido; declarar/probar modo privado cuando corresponda. | REQUIRED | A | Reporte SEO o evidencia de no indexación. | Sí | Sí |
| SEO-002 | Robots, sitemap, canonical, status, redirects y enlaces corresponden al artefacto desplegado. | REQUIRED | A, cuando es público/híbrido | Smoke SEO sobre URL real. | Sí | Sí |
| SEO-003 | Registrar conflictos con Design System/SEO/seguridad; no resolverlos silenciosamente. | REQUIRED | A, cuando existe conflicto | Registro de decisión y aprobación. | No | Sí |

### 24.12 Cierre Production Ready

| ID | Regla verificable | Severidad | Aplica | Evidencia mínima | Automatizable | Humana |
| --- | --- | --- | --- | --- | --- | --- |
| DOD-001 | Solo declarar Production Ready cuando todos los BLOCKER y REQUIRED aplicables están PASS, ningún NOT EVALUATED se presenta como PASS, deuda recomendada tiene dueño y la aprobación identifica fecha/commit/entorno/evaluador. | BLOCKER | A | Checklist firmada, matriz de evidencia y aprobación final. | Parcial | Sí |
