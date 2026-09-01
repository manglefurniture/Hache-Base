# HACHE BASE — PRODUCTION READINESS RESEARCH SOURCES

**Fecha de consulta:** 1 de septiembre de 2026, salvo indicación distinta.  
**Criterio:** prioridad a normas, organismos, documentación oficial y fuentes técnicas primarias. Las reglas de Hache Base son una adaptación proporcional; no una copia ni una declaración de conformidad total con cada fuente.

**Normalización v1.1:** no se realizó una nueva investigación general ni se cambiaron versiones. Se mantienen como referencias principales ASVS 5.0.0, WCAG 2.2, los Core Web Vitals actuales y la familia HTTP RFC 9110/9111/9112. La normalización corrigió metadatos internos de controles; no necesitó añadir una fuente externa nueva.

---

## 1. Performance y plataforma web

| Organización | Documento | URL | Área fundamentada |
| --- | --- | --- | --- |
| Google / web.dev | How the Core Web Vitals metrics thresholds were defined | https://web.dev/articles/defining-core-web-vitals-thresholds | LCP ≤2.5 s, INP ≤200 ms, CLS ≤0.1; p75 y justificación de thresholds. |
| Google / web.dev | Web Vitals | https://web.dev/articles/vitals | Métricas de campo, CWV y experiencia real. |
| Google / web.dev | Optimize Largest Contentful Paint | https://web.dev/articles/optimize-lcp | Descubrimiento/prioridad del recurso LCP. |
| Google / Lighthouse | Performance scoring | https://developer.chrome.com/docs/lighthouse/performance/performance-scoring | Uso diagnóstico de Lighthouse y límites del score agregado. |
| MDN Web Docs | Responsive images | https://developer.mozilla.org/en-US/docs/Web/HTML/Guides/Responsive_images | `srcset`, `sizes` y selección por dispositivo. |
| MDN Web Docs | `<img>` | https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/img | Dimensiones, lazy loading, alt y prevención de layout shift. |
| MDN Web Docs | Lazy loading | https://developer.mozilla.org/en-US/docs/Web/Performance/Guides/Lazy_loading | Carga diferida de recursos no críticos. |
| MDN Web Docs | Preloading content with `rel=preload` | https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Attributes/rel/preload | Preload selectivo, tipo y CORS. |
| MDN Web Docs | `font-display` | https://developer.mozilla.org/en-US/docs/Web/CSS/@font-face/font-display | Estrategias de carga de fuentes. |

## 2. Accesibilidad

| Organización | Documento | URL | Área fundamentada |
| --- | --- | --- | --- |
| W3C WAI | Web Content Accessibility Guidelines (WCAG) 2.2 | https://www.w3.org/TR/WCAG22/ | Baseline WCAG 2.2 AA y criterios verificables. |
| W3C WAI | What’s New in WCAG 2.2 | https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/ | Focus not obscured, dragging, target size, redundant entry y auth accesible. |
| W3C WAI | Understanding 2.4.11 Focus Not Obscured (Minimum) | https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum | Sticky/overlays y visibilidad del foco. |
| W3C WAI | Understanding 2.5.8 Target Size (Minimum) | https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum | Mínimo 24×24 CSS px y excepciones. |
| W3C WAI | WAI-ARIA Authoring Practices Guide | https://www.w3.org/WAI/ARIA/apg/ | Patrones de dialogs, menús, disclosures y teclado. |
| W3C | Accessible Rich Internet Applications (WAI-ARIA) 1.2 | https://www.w3.org/TR/wai-aria-1.2/ | Roles/estados ARIA y semántica. |

## 3. HTTP, caché y headers

| Organización | Documento | URL | Área fundamentada |
| --- | --- | --- | --- |
| IETF / RFC Editor | RFC 9110 — HTTP Semantics | https://www.rfc-editor.org/rfc/rfc9110.html | Métodos, status codes, idempotencia y semántica HTTP. |
| IETF / RFC Editor | RFC 9111 — HTTP Caching | https://www.rfc-editor.org/rfc/rfc9111.html | Caches y headers de control. |
| IETF / RFC Editor | RFC 9112 — HTTP/1.1 | https://www.rfc-editor.org/rfc/rfc9112.html | Retry de métodos idempotentes y fiabilidad de solicitudes. |
| MDN Web Docs | HTTP caching | https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/Caching | Aplicación práctica de caché por recursos/respuestas. |
| MDN Web Docs | Content-Security-Policy | https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy | Semántica CSP. |
| MDN Web Docs | Strict-Transport-Security | https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Strict-Transport-Security | HSTS, subdominios y precauciones. |
| MDN Web Docs | Referrer-Policy | https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Referrer-Policy | Minimización del referrer. |
| MDN Web Docs | Permissions-Policy | https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Permissions-Policy | Restricción de capacidades del navegador. |

## 4. Seguridad

| Organización | Documento | URL | Área fundamentada |
| --- | --- | --- | --- |
| OWASP | Application Security Verification Standard 5.0.0 | https://owasp.org/www-project-application-security-verification-standard/ | Marco de controles verificables y baseline proporcional; no se afirma conformidad ASVS completa. |
| OWASP Cheat Sheet Series | HTTP Security Response Headers | https://cheatsheetseries.owasp.org/cheatsheets/HTTP_Headers_Cheat_Sheet.html | CSP, HSTS, nosniff, referrer, framing y permissions. |
| OWASP Cheat Sheet Series | Content Security Policy | https://cheatsheetseries.owasp.org/cheatsheets/Content_Security_Policy_Cheat_Sheet.html | CSP como defensa en profundidad y despliegue. |
| OWASP Cheat Sheet Series | Cross-Site Request Forgery Prevention | https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html | Tokens/headers/origin, HTTPS y métodos seguros sin mutación. |
| OWASP Cheat Sheet Series | Cross Site Scripting Prevention | https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html | Output encoding/sanitización contextual. |
| OWASP Cheat Sheet Series | SQL Injection Prevention | https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html | Consultas parametrizadas y allowlists. |
| OWASP Cheat Sheet Series | Input Validation | https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html | Validación servidor, sintáctica y semántica. |
| OWASP Cheat Sheet Series | Session Management | https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html | Cookies, session fixation, TLS y lifecycle. |
| OWASP Cheat Sheet Series | Authentication | https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html | Passwords, auth y recuperación. |
| OWASP Cheat Sheet Series | Forgot Password | https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html | Tokens de recuperación, enumeración y rate limiting. |
| OWASP Cheat Sheet Series | File Upload | https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html | Allowlist, MIME/contenido, storage, tamaño y malware. |
| OWASP Cheat Sheet Series | REST Security | https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html | Authz, status, headers y APIs. |
| OWASP Cheat Sheet Series | Secrets Management | https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html | Lifecycle, acceso, rotación y fugas en CI/logs. |
| OWASP Cheat Sheet Series | Logging | https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html | Eventos de seguridad, estructura y exclusión de datos sensibles. |
| OWASP Cheat Sheet Series | Vulnerable Dependency Management | https://cheatsheetseries.owasp.org/cheatsheets/Vulnerable_Dependency_Management_Cheat_Sheet.html | Detección y triage de dependencias vulnerables. |
| OWASP Cheat Sheet Series | Software Supply Chain Security | https://cheatsheetseries.owasp.org/cheatsheets/Software_Supply_Chain_Security_Cheat_Sheet.html | CI, proveedores, automatización, monitoreo y artifacts. |
| OWASP Cheat Sheet Series | CI/CD Security | https://cheatsheetseries.owasp.org/cheatsheets/CI_CD_Security_Cheat_Sheet.html | Secretos, runners y pipeline. |
| OWASP Cheat Sheet Series | NPM Security | https://cheatsheetseries.owasp.org/cheatsheets/NPM_Security_Cheat_Sheet.html | Lockfiles, scripts y auditoría en ecosistemas npm cuando apliquen. |

## 5. Resiliencia, idempotencia y operaciones distribuidas

| Organización | Documento | URL | Área fundamentada |
| --- | --- | --- | --- |
| AWS Builders’ Library | Timeouts, retries, and backoff with jitter | https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/ | Timeouts finitos, retries limitados, backoff y jitter. |
| AWS Builders’ Library | Making retries safe with idempotent APIs | https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/ | Claves de idempotencia, resultado incierto y side effects. |
| AWS Builders’ Library | Ensuring rollback safety during deployments | https://aws.amazon.com/builders-library/ensuring-rollback-safety-during-deployments/ | Compatibilidad y seguridad de rollback. |
| Google SRE | Monitoring Distributed Systems | https://sre.google/sre-book/monitoring-distributed-systems/ | Golden signals: latencia, tráfico, errores y saturación; síntomas y alertas. |
| Google SRE | Testing for Reliability | https://sre.google/sre-book/testing-reliability/ | Pruebas como parte de fiabilidad. |
| Google SRE | Reliable Product Launches at Scale | https://sre.google/sre-book/reliable-product-launches/ | Launch readiness, ownership y verificación operativa. |

## 6. Observabilidad

| Organización | Documento | URL | Área fundamentada |
| --- | --- | --- | --- |
| OpenTelemetry | Observability primer | https://opentelemetry.io/docs/concepts/observability-primer/ | Diferencia entre disponibilidad y fiabilidad; telemetría. |
| OpenTelemetry | Signals | https://opentelemetry.io/docs/concepts/signals/ | Logs, metrics, traces y perfiles. |
| OpenTelemetry | Logs | https://opentelemetry.io/docs/concepts/signals/logs/ | Logs timestamped y estructura recomendada. |
| OpenTelemetry | Context propagation | https://opentelemetry.io/docs/concepts/context-propagation/ | Correlación entre procesos/señales. |
| W3C Trace Context | Trace Context | https://www.w3.org/TR/trace-context/ | Propagación estándar de contexto distribuido cuando se adopte tracing. |

## 7. Formularios y privacidad

| Organización | Documento | URL | Área fundamentada |
| --- | --- | --- | --- |
| MDN Web Docs | Client-side form validation | https://developer.mozilla.org/en-US/docs/Learn_web_development/Extensions/Forms/Form_validation | Constraint validation como UX, no sustituto del servidor. |
| MDN Web Docs | HTML form element | https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/form | Semántica y envío de formularios. |
| W3C | Privacy Principles | https://www.w3.org/TR/privacy-principles/ | Minimización, propósito y riesgos de divulgación/uso indebido. |
| W3C TAG | Web Platform Design Principles — Minimize user data | https://www.w3.org/TR/design-principles/#data-minimization | Solicitar solo datos necesarios y controles granulares. |

## 8. Email y webhooks

| Organización | Documento | URL | Área fundamentada |
| --- | --- | --- | --- |
| Resend | Webhook event types | https://resend.com/docs/webhooks/event-types | Diferencia entre sent/accepted, delivered, delayed, bounced, failed y suppressed. |
| Resend | Managing Webhooks | https://resend.com/docs/webhooks/introduction | Eventos de entrega, almacenamiento y alertas. |
| Resend | `email.delivered` | https://resend.com/docs/webhooks/emails/delivered | Delivered significa entrega al servidor receptor, no lectura/inbox garantizado. |
| Resend | Email bounces | https://resend.com/docs/dashboard/emails/email-bounces | Bounces temporales/permanentes y reputación. |
| Stripe | Receive events in your webhook endpoint | https://docs.stripe.com/webhooks | Firma, duplicados, selección de eventos y retries. Se usa como referencia técnica general, no como dependencia obligatoria. |
| Stripe | Process undelivered webhook events | https://docs.stripe.com/webhooks/process-undelivered-events | Persistencia, processing/processed, re-proceso e idempotencia. |

## 9. Datos, configuración y deployment

| Organización | Documento | URL | Área fundamentada |
| --- | --- | --- | --- |
| MariaDB | Backup and Restore Overview | https://mariadb.com/docs/server/server-usage/backup-and-restore/backup-and-restore-overview | Backups físicos/lógicos y restore. |
| MariaDB | Making Backups with `mariadb-dump` | https://mariadb.com/docs/server/mariadb-quickstart-guides/mariadb-backup-guide | Dumps y recuperación básica. |
| MariaDB | InnoDB | https://mariadb.com/docs/server/server-usage/storage-engines/innodb | Transacciones, constraints e integridad. |
| MariaDB | CREATE TABLE | https://mariadb.com/docs/server/server-usage/tables/create-table | Constraints, indexes y esquema. |
| Twelve-Factor App | The Twelve Factors | https://12factor.net/ | Config en entorno, build/release/run, parity, disposability y logs. |

## 10. Fuentes internas de Hache Base

Estas fuentes se usaron para comparar el estándar contra el estado actual; no fundamentan por sí solas la investigación externa.

| Fuente | Función en la auditoría |
| --- | --- |
| `DESIGN-SYSTEM-2026-FINAL.md` | Norma visual/UX/a11y/performance vigente; evita duplicación. |
| `seo/README.md` y `seo/reference/SEO-TECHNICAL-BASE-2026.md` | Norma SEO existente; se referencia en lugar de reproducir. |
| `docs/design-system/{ARCHITECTURE,INITIAL-AUDIT,FINAL-REPORT}.md` | Arquitectura y evidencia histórica de la implementación del Design System. |
| `security/` | Helpers y límites de auth, authz, CSRF, API, rate limiting y headers. |
| `integrations/email/` y `integrations/payments/` | Patrones actuales de aceptación, firma, idempotencia, credenciales y efectos secundarios. |
| `database/`, `deployment/`, `tests/`, `.github/workflows/` | Evidencia de migración, backup, rollback, tests, CI y deploy. |

## 11. Notas de interpretación

1. Los thresholds CWV se adoptan como clasificación oficial “good”, idealmente p75; no se inventan budgets universales de bytes para aplicaciones distintas.
2. WCAG 2.2 AA es un objetivo verificable combinado automático/humano; el test estático de Core no prueba una página derivada.
3. ASVS 5.0.0 orienta el baseline proporcional; el documento no afirma que Hache Base o sus derivados estén certificados ASVS.
4. Documentación de Resend/Stripe se usa para demostrar semánticas reales de proveedores: ACK, delivery, duplicates y retries. Cada adapter debe obedecer el contrato de su proveedor real.
5. OpenTelemetry se usa como vocabulario de observabilidad; no se exige instalar su SDK en Core.
6. Twelve-Factor es una referencia arquitectónica reconocida, no una norma reciente ni suficiente por sí sola para producción.
