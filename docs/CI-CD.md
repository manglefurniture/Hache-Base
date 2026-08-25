# CI/CD

## CI

`.github/workflows/ci.yml` ejecuta comprobaciones de PHP, shell, pruebas reutilizables y carga los esquemas base sobre MariaDB antes de aceptar cambios.

Cada proyecto debe añadir sus propias pruebas de negocio, roles, sedes y migraciones.

## CD

`deploy-template.yml` es deliberadamente **gated**. No despliega mientras la variable de repositorio `ENABLE_PRODUCTION_DEPLOY` no sea `true` y el entorno `production` no tenga sus secretos/configuración.

Configurar antes de habilitar:

- `production` como GitHub Environment con aprobación manual cuando corresponda;
- `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`, `SSH_KNOWN_HOSTS` y opcional `DEPLOY_PORT` como secrets;
- `DEPLOY_PATH` como variable;
- runner de despliegue probado primero en staging;
- backup, health check y rollback comprobados.

No reutilizar una clave SSH personal. Usar una credencial de despliegue de alcance mínimo y rotarla/retirarla cuando cambie el modelo de acceso.

## Flujo

`PR -> CI -> merge -> staging -> aprobación -> workflow_dispatch(commit exacto) -> preflight -> backup -> deploy -> tests -> health -> DEPLOY_OK`

El despliegue remoto recibe un commit exacto; no despliega simplemente "lo último" sin identificar qué versión se está instalando.
