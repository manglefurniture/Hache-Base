# Hache-Base

Base técnica reutilizable para proyectos de **Hache Interactive**.

## Propósito

Hache-Base reúne patrones, documentación, plantillas y componentes genéricos que permitan iniciar nuevos sistemas con una arquitectura más segura, comprobable y mantenible.

Nace de las lecciones de la auditoría integral de Hache Natación, pero **no es una copia de Hache Natación**. Todo componente incorporado aquí debe ser independiente del negocio y configurable para distintos proyectos.

## Principios

1. Seguridad desde el inicio.
2. Roles y permisos definidos antes de construir pantallas.
3. Soporte multiempresa/multisede cuando el proyecto lo requiera.
4. Migraciones pequeñas, cronológicas y comprobables.
5. Pruebas desde los primeros flujos funcionales.
6. Configuración separada del código.
7. Backups y rollback antes de producción.
8. Integraciones externas desacopladas del núcleo.
9. Cambios pequeños y trazables.
10. Nunca almacenar secretos, credenciales o datos reales de clientes.

## Estructura prevista

- `docs/` — arquitectura, reglas y procedimientos.
- `templates/` — archivos base para nuevos proyectos.
- `database/` — migraciones y patrones de integridad.
- `security/` — patrones reutilizables de seguridad.
- `integrations/` — integraciones desacopladas, como n8n.
- `tests/` — pruebas estáticas, smoke, integración y fixtures.
- `deployment/` — preflight, backup, despliegue y rollback.

## Estado

**Fase 1 — Fundación del repositorio: en implementación.**

La primera versión estable será `Hache-Base v1.0` cuando un proyecto nuevo pueda partir de esta base con configuración, seguridad, migraciones, pruebas, backup, despliegue y rollback sin copiar lógica específica de otro negocio.
