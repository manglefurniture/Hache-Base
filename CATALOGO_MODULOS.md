# Catálogo de módulos — Hache-Base v1.0

Índice funcional para elegir capacidades sin tener que recordar nombres de archivos.

| Módulo | Estado | Qué resuelve | Cuándo usarlo | Referencia |
| --- | --- | --- | --- | --- |
| Arquitectura base | Listo | Separa interfaz, aplicación, dominio, datos e integraciones | Todos los proyectos de aplicación | `docs/ARQUITECTURA.md` |
| Multisede / multiempresa | Listo | Aísla datos y operaciones por organización o sede | Cadenas, sucursales, escuelas, gimnasios, clínicas, restaurantes, spas | `docs/MULTISEDE.md` |
| Roles y permisos | Listo | Define quién puede hacer qué y en qué contexto | Sistemas con más de un tipo de usuario | `docs/ROLES-Y-PERMISOS.md` |
| Reglas de negocio | Listo | Evita reglas dispersas o contradictorias | Sistemas con lógica operativa | `docs/REGLAS-DE-NEGOCIO.md` |
| Seguridad web/API | Listo | Sesión, autorización, CSRF, Bearer, rate limit, JSON y headers | Paneles, formularios y APIs | `security/README.md` |
| Auditoría de mutaciones | Listo | Registra quién cambió qué, cuándo y en qué contexto | Pagos, inventario, citas, usuarios, configuración | `docs/AUDITORIA.md` |
| Migraciones e integridad | Listo | Cambios de esquema pequeños, probables e idempotentes | Proyectos con MariaDB | `database/MIGRATIONS.md` |
| Modelo de servicios | Plantilla lista | Organizaciones, sedes, usuarios, clientes, servicios, planes, horarios, pagos y sesiones | Academias, spas, gimnasios, clínicas y servicios recurrentes | `database/modules/README.md` |
| Operaciones recurrentes | Plantilla opcional | Asistencia, ausencias y sesiones de reemplazo | Negocios que realmente manejen esas reglas | `database/modules/recurring-operations.sql` |
| Teléfonos E.164 | Listo | Normalización internacional y compatibilidad mexicana histórica +521 | CRM, WhatsApp, clientes internacionales | `src/common/PhoneNormalizer.php` |
| Utilidades comunes | Listo | IDs, email, texto y dinero en centavos | Formularios y lógica común | `src/common/` |
| n8n | Listo como patrón | API privada, Bearer, Nginx/PHP-FPM y backup Docker/SQLite | Automatizaciones desacopladas | `integrations/n8n/README.md` |
| Pruebas | Listo como base | Sintaxis, unitarias, smoke e integración | Todos los proyectos con lógica crítica | `tests/README.md` |
| Backup / rollback | Listo como plantilla | Respaldo MariaDB, commit y reversión de código | Sistemas desplegados en servidor | `deployment/BACKUP-ROLLBACK.md` |
| Runner de despliegue | Listo como plantilla | Preflight → backup → commit → migraciones → tests → health | VPS/producción | `deployment/README.md` |
| Configuración / secretos | Listo | Separa código de credenciales y entorno | Todos los despliegues | `docs/CONFIGURATION.md` |
| Development / staging / production | Listo | Separa prueba de producción | Proyectos con datos/operaciones críticas | `docs/ENVIRONMENTS.md` |
| CI | Listo | PHP, shell, pruebas y MariaDB automáticos | Repositorios derivados | `.github/workflows/ci.yml` |
| CD a VPS | Plantilla gated | Despliegue manual aprobado por commit exacto | Solo tras configurar staging, secrets y Environment | `.github/workflows/deploy-template.yml` |
| Bootstrap de proyecto | Listo | Selección de módulos y perfil inicial | Al arrancar un nuevo proyecto | `docs/START-NEW-PROJECT.md` |

## Cómo pedir reutilización

No hace falta mencionar archivos. Ejemplos:

- "Usa Hache-Base para un restaurante con cuatro sucursales."
- "Aplica multisede, roles, seguridad y auditoría de Hache-Base."
- "Este proyecto no necesita multisede; usa seguridad, pagos, auditoría y despliegue."

Al recibir una petición así, consultar este catálogo, revisar la documentación de los módulos elegidos y adaptar configuración/reglas al negocio.

**Reutilizable no significa copiar a ciegas.** Los esquemas de `database/modules/` y scripts de despliegue son plantillas que requieren configuración y pruebas del proyecto destino.

## Regla de mantenimiento

Cuando un nuevo proyecto produzca una solución genérica bien probada, extraerla a Hache-Base eliminando nombres, datos y reglas exclusivas del negocio; documentarla, probarla y añadirla a este catálogo.
