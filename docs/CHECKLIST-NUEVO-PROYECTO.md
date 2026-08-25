# Checklist para un nuevo proyecto

Completar antes de desarrollar los flujos principales.

## Negocio

- [ ] Definir objetivo del sistema.
- [ ] Identificar tipos de usuario.
- [ ] Definir si existen empresas, sucursales o sedes.
- [ ] Identificar servicios, productos o planes.
- [ ] Documentar reglas críticas del negocio.
- [ ] Identificar entidades cuyo estado dependa de fecha/hora y definir su regla temporal canónica.
- [ ] Definir la zona horaria operativa del negocio o de cada contexto cuando aplique.

## Acceso y permisos

- [ ] Definir roles.
- [ ] Crear matriz de permisos por rol.
- [ ] Definir qué datos puede consultar cada rol.
- [ ] Definir qué operaciones puede modificar cada rol.
- [ ] Determinar si los datos deben aislarse por sede/organización.
- [ ] Verificar que los roles de solo lectura no produzcan escrituras indirectas.

## Datos

- [ ] Diseñar entidades principales y relaciones.
- [ ] Definir restricciones de integridad.
- [ ] Definir estrategia de migraciones.
- [ ] Identificar datos personales o sensibles.
- [ ] Definir política inicial de retención.
- [ ] Si se persisten estados derivados del tiempo, documentar cómo se reconcilian y cuál es la fuente de verdad.
- [ ] Para pagos/obligaciones, definir la identidad exacta del recurso que evita duplicados.

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
- [ ] Probar fronteras temporales: antes de inicio, inicio, final y día posterior.
- [ ] Probar que vistas distintas muestran el mismo estado para el mismo recurso.
- [ ] Probar que la UI preventiva no sustituye el rechazo del servidor en acciones inválidas/duplicadas.

## Infraestructura

- [ ] Definir development, staging y production.
- [ ] Configurar `APP_TIMEZONE` o el contexto horario equivalente.
- [ ] Preparar backup antes de despliegues.
- [ ] Documentar rollback.
- [ ] Definir monitoreo mínimo.
- [ ] Identificar integraciones externas y mantenerlas desacopladas.

## Antes del primer despliegue

- [ ] No existen secretos versionados.
- [ ] Las migraciones fueron probadas fuera de producción.
- [ ] Los permisos fueron comprobados.
- [ ] La zona horaria operativa fue verificada contra la del servidor.
- [ ] Los estados temporales cambian correctamente en sus fechas frontera.
- [ ] Existe backup recuperable.
- [ ] Existe procedimiento de rollback.
- [ ] Pasan las pruebas críticas.
- [ ] Pasa el health check.
