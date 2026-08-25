# Deployment

Hache-Base adopta un despliegue verificable y reversible.

## Flujo objetivo

1. Preflight.
2. Backup.
3. Fijar/verificar versión o commit.
4. Actualizar código.
5. Ejecutar migraciones.
6. Ejecutar pruebas críticas.
7. Ejecutar health checks.
8. Confirmar `DEPLOY_OK`.
9. Si falla una etapa crítica, detener y disponer de rollback.

Los scripts reutilizables se incorporarán después de separar cualquier supuesto específico del servidor o negocio de origen.
