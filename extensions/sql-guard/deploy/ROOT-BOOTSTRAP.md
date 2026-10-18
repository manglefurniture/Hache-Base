# SQL Guard — bootstrap de cuentas y permisos amplios controlados

Este paso prepara la infraestructura para que el agente GPT **pueda llegar a
administrar ampliamente proyectos, servicios y bases de datos**, sin entregar
una shell root permanente al proceso que recibe mensajes no confiables.

## Niveles de operación previstos

1. **Diagnóstico y operaciones ordinarias:** servicios, logs, métricas,
   mantenimiento no destructivo y despliegue desde GitHub mediante ejecutores
   autorizados. Algunas capacidades requerirán nuevos adaptadores.
2. **Escrituras SQL controladas:** el SQL Guard actual incluye UPDATE/DELETE
   tipados, límites y aprobaciones. Para INSERT, DDL y migraciones se necesitará
   un nuevo ejecutor con operación tipada, política propia, preview y rollback.
   No asumir que la política actual cubre todas las tareas.
3. **Administración privilegiada:** se implementará mediante un broker separado
   con acciones allowlisted, registro de auditoría, respaldo y aprobación
   autenticada por passkey cuando pueda afectar disponibilidad, permisos o datos.
   **No existe todavía** y no se debe simular con sudo ALL.

El objetivo es que el agente pueda **solicitar y completar** tareas
administrativas reales, no bloquear su operación por defecto. Las acciones
peligrosas requerirán que el propietario confirme desde fuera del chat.

## Preparación por ConnectBot (root ya existente)

Después del merge, usar los **dos artefactos exactos de GitHub**:
- \`bootstrap-staging-root.sh\`
- \`sqlguard-tmpfiles.conf.example\`

Deben estar juntos en una carpeta temporal de entrega, transferidos desde el
commit verificado y sin editarlos en el VPS.

\`\`\`bash
bash bootstrap-staging-root.sh --check
# Después de revisar la salida con el propietario:
bash bootstrap-staging-root.sh --apply
\`\`\`

El script requiere root **solo para \`--apply\`** y hace únicamente:
- crea \`sqlguard-approval\` y \`sqlguard-runner\` sin shell interactiva;
- crea \`sqlguard-store\` (privado) y \`sqlguard-callers\` (solicitantes);
- añade \`gpt-agent\` al grupo de llamadas, **nunca al grupo del almacén**;
- prepara directorios aislados y una regla de tmpfiles para \`/run/sqlguard\`.

No modifica sudoers, bases de datos, despliegues, archivos secretos, Nginx,
unidades systemd ni servicios existentes. Es idempotente para identidades y
directorios creados con los permisos esperados; aborta ante rutas inusuales
o permisos inseguros. Reejecutarlo no equivale a habilitar el servicio.

**El agente GPT en ejecución no recibirá el grupo nuevo hasta reiniciar su
servicio.** El reinicio se planificará en una etapa posterior.

## Gates pendientes

- Deploy firmado de código GitHub al runtime independiente.
- Almacén compartido sin lectura/escritura para \`gpt-agent\`.
- Claves configuradas por administrador **fuera del chat**.
- Respaldo restaurable independiente; prueba real de WebAuthn en Android.
- Validación SQL con usuarios separados y prueba de rollback.
- Implementación del broker privilegiado, revisión y tests antes de ampliar
  capacidades del agente a servicios/sistema.
- Cambiar permisos MariaDB directos solo después de comprobar la nueva vía.

Mantener \`aprobaciones.hacheinteractive.com\` devolviendo HTTP 503 durante
esta preparación. \`deploy-hache\` conserva su sudo restringido actual.
