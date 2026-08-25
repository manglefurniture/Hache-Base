# Hache-Base

Base técnica reutilizable para proyectos de **Hache Interactive**.

## Estado

**Hache-Base v1.0 — base implementada.**

Incluye arquitectura, multisede, permisos, seguridad, auditoría, migraciones, modelos opcionales, utilidades, estados temporales, n8n, pruebas, backup/rollback, despliegue, configuración, staging y plantillas CI/CD.

El CD de producción queda deliberadamente deshabilitado hasta que cada proyecto configure su GitHub Environment, secretos, staging y VPS.

## Propósito

Hache-Base reúne patrones, documentación, plantillas y componentes genéricos para iniciar sistemas con una arquitectura más segura, comprobable y mantenible.

Nace de las lecciones de la auditoría integral de Hache Natación, pero **no es una copia de Hache Natación**. Todo componente debe ser independiente del negocio y configurable.

## Empezar

1. Leer `docs/START-NEW-PROJECT.md`.
2. Completar `templates/PROJECT-PROFILE.md` y `docs/CHECKLIST-NUEVO-PROYECTO.md`.
3. Consultar `CATALOGO_MODULOS.md`.
4. Seleccionar únicamente los módulos que aplican.
5. Convertir las plantillas elegidas en la implementación específica del nuevo proyecto.
6. Añadir reglas y pruebas propias antes de producción.

## Principios

1. Seguridad desde el inicio.
2. Roles y permisos antes de construir pantallas.
3. Multisede solo cuando el negocio lo requiera, con aislamiento real.
4. Migraciones pequeñas, cronológicas y comprobables.
5. Pruebas desde los primeros flujos funcionales.
6. Configuración, secretos y zona horaria operativa separados de supuestos del servidor.
7. Estados temporales derivados desde datos fuente y consistentes entre vistas.
8. Backups y rollback antes de producción.
9. Integraciones externas desacopladas del núcleo.
10. Cambios pequeños y trazables.
11. Nunca almacenar secretos, credenciales o datos reales de clientes en esta base.

## Estructura

- `docs/` — arquitectura, reglas, configuración, entornos, integridad temporal y bootstrap.
- `templates/` — perfiles y archivos de referencia.
- `database/` — migraciones, integridad y modelos opcionales.
- `security/` — patrones reutilizables de seguridad.
- `src/` — módulos PHP genéricos, como auditoría y utilidades.
- `integrations/` — integraciones desacopladas, como n8n.
- `tests/` — sintaxis, pruebas básicas, fronteras temporales, smoke e integración.
- `deployment/` — preflight, backup, despliegue, health y rollback.
- `.github/workflows/` — CI y plantilla gated de despliegue a producción.

## Regla de oro

**Hache-Base es una caja de herramientas, no un proyecto que se clona y se renombra.**

Para un negocio nuevo se seleccionan capacidades del catálogo y se construye encima únicamente la lógica específica que falta.
