# Hache-Base

Base técnica reutilizable para proyectos de **Hache Interactive**.

## Estado

**Hache-Base v1.0 — base implementada.**

Incluye arquitectura, Design System 2026 Core → Theme → Extensions, Production Readiness v1.1, multisede, permisos, seguridad, auditoría, migraciones, modelos opcionales, utilidades, estados temporales, contrato de estados asíncronos, inbox/outbox/idempotency opt-in, patrones UI, correo transaccional HTTPS, pagos/webhooks con credenciales versionadas, n8n, pruebas, backup/rollback, despliegue, configuración, staging y plantillas CI/CD.

El CD de producción queda deliberadamente deshabilitado hasta que cada proyecto configure su GitHub Environment, secretos, staging y VPS.

## Propósito

Hache-Base reúne patrones, documentación, plantillas y componentes genéricos para iniciar sistemas con una arquitectura más segura, comprobable y mantenible.

Nace de las lecciones de la auditoría integral de Hache Natación y de soluciones reutilizables validadas en proyectos posteriores, pero **no es una copia de ningún proyecto**. Todo componente debe ser independiente del negocio y configurable.

## Empezar

1. Leer `docs/START-NEW-PROJECT.md`.
2. Completar `templates/PROJECT-PROFILE.md` y `docs/CHECKLIST-NUEVO-PROYECTO.md`.
3. Consultar `CATALOGO_MODULOS.md`.
4. Para proyectos que avanzan hacia producción, leer `docs/production-readiness/README.md`, declarar nivel A/B/C y completar `templates/CRITICAL-USER-FLOWS.md`.
5. Seleccionar únicamente los módulos que aplican.
6. Convertir las plantillas elegidas en la implementación específica del nuevo proyecto.
7. Añadir reglas, pruebas y evidencia propia antes de producción.

## Principios

1. Seguridad desde el inicio.
2. Roles y permisos antes de construir pantallas.
3. Multisede solo cuando el negocio lo requiera, con aislamiento real.
4. Migraciones pequeñas, cronológicas y comprobables.
5. Pruebas desde los primeros flujos funcionales.
6. Configuración, secretos, egress y zona horaria operativa separados de supuestos del servidor.
7. Estados temporales derivados desde datos fuente y consistentes entre vistas.
8. Backups y rollback antes de producción.
9. Integraciones externas desacopladas del núcleo, autenticadas e idempotentes cuando puedan repetirse.
10. Credenciales externas rotables mediante versiones inmutables cuando existan operaciones históricas que deban seguir conciliándose.
11. Patrones UI reutilizables deben ser opt-in, accesibles y no depender de nombres ni reglas de un negocio concreto.
12. Cambios pequeños y trazables.
13. Nunca almacenar secretos, credenciales o datos reales de clientes en esta base.
14. Design System Foundation → Semantic → Component: calidad reusable sin imponer apariencia.
15. Dimensional es el preset visual recomendado; Immersive siempre es opt-in y justificado.
16. Production Ready es un estado demostrable: Standard → Checklist → evidencia por CUF; un build, un 200 o un backup sin restore no bastan.
17. En operaciones asíncronas, `accepted` no equivale a `confirmed`; los resultados ambiguos deben reconciliarse antes de reintentar a ciegas.
18. Inbox/outbox/claims son Extensions opt-in: dedupe, concurrencia y reprocess deben demostrarse en servidor sin obligar a todos los proyectos a operar una cola.

## Estructura

- `docs/` — arquitectura, reglas, configuración, entornos, integridad temporal, UI, Production Readiness y bootstrap.
- `templates/` — perfiles, Critical User Flows, ledger de operaciones asíncronas, adopción inbox/outbox y archivos de referencia.
- `database/` — migraciones, integridad y modelos opcionales, incluida la plantilla P0-06 no automática.
- `security/` — patrones reutilizables de seguridad y contrato de respuesta API.
- `src/` — módulos genéricos y componentes reutilizables, incluyendo Core, Themes, contrato de Extensions UI, request context, logging mínimo y estados asíncronos.
- `integrations/` — async delivery opt-in, correo HTTPS, pagos/webhooks, n8n y otras integraciones desacopladas.
- `tests/` — sintaxis, pruebas básicas, UI, fronteras temporales, estados asíncronos, persistencia idempotente, integración, readiness y smoke.
- `deployment/` — preflight, backup, despliegue, liveness/readiness y rollback.
- `.github/workflows/` — CI y plantilla gated de despliegue a producción.

## Production Readiness

La norma oficial vive en `docs/production-readiness/PRODUCTION-READINESS-STANDARD.md` v1.1. El registro canónico de su sección 24 define IDs, severidad, aplicabilidad y evidencia. La Checklist es una proyección y no puede reinterpretarlo.

La primera fase Core implementada se limitó a P0-01, P0-02, P0-03, P0-04 y P0-09: documentación, plantilla CUF, error contract/request ID, logging estructurado mínimo y separación liveness/readiness/smoke.

P0-05 está implementado mediante `AsyncOperationState`, documentación, plantilla de operation/event ledger y fixtures offline.

P0-06 está implementado como **Extension opt-in** mediante contrato de inbox/outbox/idempotency claim, schema plantilla MariaDB y regresiones de duplicado, concurrencia, out-of-order y reprocess. No activa proveedores, workers, Redis ni colas globales.

Esto **no** significa que cualquier proyecto derivado sea automáticamente Production Ready; debe evaluar sus controles aplicables con evidencia real.

## Regla de oro

**Hache-Base es una caja de herramientas, no un proyecto que se clona y se renombra.**

Para un negocio nuevo se seleccionan capacidades del catálogo y se construye encima únicamente la lógica específica que falta.
