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
- [ ] Para pagos externos, definir referencia local, ID único del proveedor, importe/moneda esperados y estados finales.
- [ ] Si existe inventario/cupo reservable, definir TTL y liberación idempotente antes de checkout.
- [ ] Identificar datos que puedan formar parte de cierres, facturas, cortes o snapshots y definir cómo se preservará su evidencia histórica después de invalidaciones/correcciones.

## Privacidad

- [ ] Si se recopilan datos personales, identificar al responsable legal del tratamiento.
- [ ] Definir el domicilio o dato de identificación requerido por la política aplicable sin inventar información.
- [ ] Definir un canal específico para solicitudes de acceso, rectificación, cancelación, oposición o eliminación cuando corresponda.
- [ ] Enlazar el aviso de privacidad desde los puntos públicos donde se recopilan datos.
- [ ] No incorporar datos personales reales del responsable en Hache-Base; mantenerlos en la configuración/documentación del proyecto destino.

## Seguridad

- [ ] Elegir mecanismo de autenticación.
- [ ] Definir autorización centralizada.
- [ ] Proteger formularios contra CSRF cuando corresponda.
- [ ] Definir protección y autenticación de APIs.
- [ ] Separar secretos del código mediante variables de entorno.
- [ ] Definir rate limiting para rutas expuestas cuando corresponda.
- [ ] Para webhooks, definir mecanismo de firma/autenticación y secreto independiente.

## Integraciones externas

- [ ] Identificar proveedor, dirección del flujo de datos y datos compartidos.
- [ ] Verificar puertos/protocolo de salida desde staging/producción; no asumir SMTP u otro egress.
- [ ] Definir timeouts, reintentos y comportamiento degradado.
- [ ] Definir rotación y alcance mínimo de API keys/tokens.
- [ ] Si hay correo transaccional, verificar el dominio/subdominio remitente y autenticación DNS requerida.
- [ ] Si hay pagos, definir consulta autoritativa al proveedor después del webhook.
- [ ] Documentar cómo desactivar la integración sin romper el producto principal.

## Calidad

- [ ] Definir lint y validaciones estáticas.
- [ ] Crear pruebas de los flujos críticos.
- [ ] Crear pruebas por rol y sede cuando aplique.
- [ ] Preparar fixtures que no alteren datos reales.
- [ ] Definir health check.
- [ ] Probar fronteras temporales: antes de inicio, inicio, final y día posterior.
- [ ] Probar que vistas distintas muestran el mismo estado para el mismo recurso.
- [ ] Probar que la UI preventiva no sustituye el rechazo del servidor en acciones inválidas/duplicadas.
- [ ] En acciones asíncronas sensibles, probar que una respuesta antigua no puede modificar una operación o modal posterior.
- [ ] Para webhooks/jobs repetibles, probar idempotencia y eventos fuera de orden.
- [ ] Para pagos, probar mismatch de importe/moneda y que un fallo de notificación no revierta el estado financiero.
- [ ] Para reservas, probar expiración y carrera concurrente por la última unidad/cupo.

## Infraestructura

- [ ] Definir development, staging y production.
- [ ] Configurar `APP_TIMEZONE` o el contexto horario equivalente.
- [ ] Preparar backup antes de despliegues.
- [ ] Documentar rollback.
- [ ] Definir monitoreo mínimo.
- [ ] Identificar integraciones externas y mantenerlas desacopladas.
- [ ] Documentar dónde se cargan secretos en producción (`.env`, PHP-FPM/systemd o gestor equivalente).

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
- [ ] Las integraciones críticas tienen conectividad confirmada desde el host real.
- [ ] Si hay correo, existe una prueba real de aceptación/entrega con el dominio remitente configurado.
- [ ] Si hay pagos, la firma del webhook y la idempotencia fueron comprobadas fuera de producción.

## Antes de mergear cambios relevantes

- [ ] CI/Quality está verde.
- [ ] Los hallazgos de revisión están clasificados como corregidos, ya resueltos, no aplicables o pendientes de decisión humana.
- [ ] Las correcciones de review tienen regresiones proporcionales cuando aportan valor.
- [ ] No se amplió innecesariamente el alcance con auditorías, refactors u optimizaciones no solicitadas.
- [ ] Después del merge existe un plan explícito de deploy y smoke test cuando el proyecto tenga producción.
