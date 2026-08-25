# Checklist para un nuevo proyecto

Completar antes de desarrollar los flujos principales.

## Negocio

- [ ] Definir objetivo del sistema.
- [ ] Identificar tipos de usuario.
- [ ] Definir si existen empresas, sucursales o sedes.
- [ ] Identificar servicios, productos o planes.
- [ ] Documentar reglas críticas del negocio.

## Acceso y permisos

- [ ] Definir roles.
- [ ] Crear matriz de permisos por rol.
- [ ] Definir qué datos puede consultar cada rol.
- [ ] Definir qué operaciones puede modificar cada rol.
- [ ] Determinar si los datos deben aislarse por sede/organización.

## Datos

- [ ] Diseñar entidades principales y relaciones.
- [ ] Definir restricciones de integridad.
- [ ] Definir estrategia de migraciones.
- [ ] Identificar datos personales o sensibles.
- [ ] Definir política inicial de retención.

## Seguridad

- [ ] Elegir mecanismo de autenticación.
- [ ] Definir autorización centralizada.
- [ ] Proteger formularios contra CSRF cuando corresponda.
- [ ] Definir protección y autenticación de APIs.
- [ ] Separar secretos del código mediante variables de entorno.
- [ ] Definir rate limiting para rutas expuestas cuando corresponda.

## Calidad

- [ ] Definir lint y validaciones estáticas.
- [ ] Crear pruebas de los flujos críticos.
- [ ] Crear pruebas por rol y sede cuando aplique.
- [ ] Preparar fixtures que no alteren datos reales.
- [ ] Definir health check.

## Infraestructura

- [ ] Definir development, staging y production.
- [ ] Preparar backup antes de despliegues.
- [ ] Documentar rollback.
- [ ] Definir monitoreo mínimo.
- [ ] Identificar integraciones externas y mantenerlas desacopladas.

## Antes del primer despliegue

- [ ] No existen secretos versionados.
- [ ] Las migraciones fueron probadas fuera de producción.
- [ ] Los permisos fueron comprobados.
- [ ] Existe backup recuperable.
- [ ] Existe procedimiento de rollback.
- [ ] Pasan las pruebas críticas.
- [ ] Pasa el health check.
