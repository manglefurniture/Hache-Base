# Catálogo de módulos — Hache-Base

Este archivo es el índice funcional de Hache-Base. Antes de iniciar un proyecto, úsalo para elegir capacidades sin tener que recordar nombres de archivos.

| Módulo | Estado | Qué resuelve | Cuándo usarlo | Referencia principal |
| --- | --- | --- | --- | --- |
| Arquitectura base | Listo | Separa interfaz, aplicación, dominio, datos e integraciones | Todos los proyectos de aplicación | `docs/ARQUITECTURA.md` |
| Multisede / multiempresa | Listo | Aísla datos y operaciones por organización o sede | Cadenas, sucursales, escuelas, gimnasios, clínicas, restaurantes, spas | `docs/MULTISEDE.md` |
| Roles y permisos | Listo | Define quién puede hacer qué y sobre qué contexto | Sistemas con más de un tipo de usuario | `docs/ROLES-Y-PERMISOS.md` |
| Reglas de negocio | Listo | Evita reglas dispersas o contradictorias | Todo sistema con lógica operativa | `docs/REGLAS-DE-NEGOCIO.md` |
| Seguridad web/API | Listo | Sesión, autorización, CSRF, Bearer, rate limiting, JSON y headers | Aplicaciones con panel, formularios o API | `security/README.md` |
| Auditoría de mutaciones | Listo | Registra quién cambió qué, cuándo y en qué contexto | Pagos, inventario, citas, usuarios, configuración y operaciones administrativas | `docs/AUDITORIA.md` |
| Configuración por entorno | Base lista | Separa configuración y secretos del código | Todos los proyectos desplegables | `.env.example` |
| Migraciones | Base definida | Controla cambios de esquema de forma reproducible | Proyectos con base de datos | `database/README.md` |
| Integraciones | Base definida | Desacopla servicios externos del núcleo | n8n, correo, mensajería, APIs | `integrations/README.md` |
| Pruebas | Base definida | Establece capas de pruebas y fixtures | Todos los proyectos con lógica crítica | `tests/README.md` |
| Despliegue y rollback | Base definida | Define despliegue verificable y reversible | Proyectos en servidor/producción | `deployment/README.md` |

## Cómo pedir reutilización

No hace falta mencionar archivos. Ejemplos:

- "Usa Hache-Base para un restaurante con cuatro sucursales."
- "Aplica multisede, roles, seguridad y auditoría de Hache-Base."
- "Este proyecto no necesita multisede; usa seguridad, auditoría y despliegue."

Antes de reutilizar un módulo se debe revisar su documentación y adaptar configuración, nombres de roles, modelo de datos y políticas al nuevo negocio. **Reutilizable no significa copiar a ciegas.**

## Estado del catálogo

El catálogo se actualizará cada vez que un módulo pase de documentación/base a implementación reutilizable.
