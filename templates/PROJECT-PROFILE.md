# Perfil del proyecto

## Identidad

- Nombre:
- Tipo de negocio:
- Objetivo principal:
- Usuarios esperados:
- Zona horaria operativa (`APP_TIMEZONE`):

## Organización

- ¿Multiempresa?: sí / no
- ¿Multisede?: sí / no
- Sedes iniciales:
- ¿Existen administradores globales?:
- ¿Todas las sedes comparten zona horaria?: sí / no / no aplica

## Roles

| Rol | Puede ver | Puede crear | Puede modificar | Puede eliminar/invalidar | Alcance |
| --- | --- | --- | --- | --- | --- |
| | | | | | |

Completar también `PERMISSION-MATRIX.md`.

## Datos principales

- Clientes/usuarios finales:
- Servicios/productos:
- Agenda/horarios:
- Pagos:
- Otros:

## Reglas críticas

1.
2.
3.

## Estados temporales

- ¿Existen entidades cuyo estado dependa de fecha/hora?: sí / no
- Entidades/rangos:
- Regla canónica por entidad:
- ¿Se persistirá el estado derivado?: sí / no
- Si se persiste, mecanismo de reconciliación y permiso requerido:
- Vistas/reportes que deben mostrar el mismo estado:

## Obligaciones y duplicados

- Obligaciones que no permiten duplicado activo:
- Identidad exacta de cada obligación (actor + recurso + tipo + periodo/estado):
- Defensa de servidor/transaccional prevista:

## Integraciones

- n8n:
- correo:
- mensajería:
- APIs externas:

## SEO / superficie pública

- `SEO_MODE`: public / private-app / hybrid / none
- Dominio/host canónico esperado:
- Rutas públicas indexables:
- Rutas privadas/no indexables:
- ¿SEO local / ubicaciones reales?: sí / no
- ¿Search Console/Bing Webmaster Tools?: sí / no / pendiente
- ¿Schema previsto?:
- ¿Política de bots de búsqueda/IA definida?: sí / no
- Excepciones al Minimum SEO Baseline:

## Módulos Hache-Base seleccionados

- [ ] Arquitectura base
- [ ] Multisede/multiempresa
- [ ] Roles/permisos
- [ ] Estados temporales e integridad entre vistas
- [ ] Seguridad web/API
- [ ] Auditoría
- [ ] Modelo de servicios recurrentes
- [ ] Operaciones recurrentes (asistencia/ausencias/reemplazos)
- [ ] Utilidades comunes
- [ ] n8n
- [ ] SEO técnico / Minimum SEO Baseline
- [ ] Pruebas
- [ ] Backup/rollback
- [ ] Runner de despliegue
- [ ] Staging
- [ ] CI/CD

## Entornos

- Development:
- Staging:
- Production:

## Criterio de listo para producción

- Pruebas críticas:
- Fronteras temporales/zona horaria:
- Consistencia entre vistas:
- SEO Baseline (si `public`/`hybrid`):
- Backup/restauración:
- Health check:
- Aprobación requerida:
