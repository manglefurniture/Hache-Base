# Plan de activación SQL Guard en MariaDB

Estado: diseño; **no desplegado**.

## Amenaza que resolvemos
La cuenta Linux `gpt-agent` usa MariaDB `unix_socket` y tiene UPDATE y DELETE directamente en cinco bases. Ninguna validación Python impide que ejecute `mariadb` por separado. Por tanto, la primera condición de éxito es **eliminar el acceso directo de escritura** una vez exista un servicio intermedio íntegramente probado.

## Roles independientes previstos
- `gpt-agent`: consultas SELECT/SHOW/EXPLAIN, sin UPDATE/DELETE/ALTER/CREATE en producción tras cutover.
- `sqlguard-runner`: cuenta de sistema sin acceso interactivo; permisos de BD para cambios *específicos*, sin DROP ni GRANT; nunca se expone contraseña ni socket privilegiado a `gpt-agent`.
- `sqlguard-approver`: mecanismo de aprobación fuera del agente, con identidad humana, hash del cambio (BD, tabla, columnas, valores, condición), caducidad, nonce de un solo uso y auditoría. Ninguna aprobación recibida como argumento de GPT se considera válida.
- Respaldos: mantener el job actual; ejecución previa, salida `BACKUP_OK`, checksum, y comprobación de espacio libre.

## Secuencia segura
1. Implementar adaptador MariaDB usando transacciones y bloqueo consistente (no portar `BEGIN IMMEDIATE`, exclusivo de SQLite).
2. Crear pruebas en contenedor aislado: dos sesiones concurrentes, recuentos justo antes de escribir, rollback tras fallo, SQL parametrizado, privilegios y conexión con permisos mínimos, triggers, restricciones FK.
3. Verificar que la configuración completa del runner y credenciales son propiedad de root; servicio de sistema sin shell, acceso delimitado y logging.
4. Comprobar que la vía de aprobación humana externa no permite que el agente se autoapruebe.
5. En ambiente de prueba, revocar los permisos de escritura del agente y verificar rechazo de SQL directo y funcionamiento del runner.
6. Backups + punto de restauración, ventana de activación y plan de rollback.
7. Activación **coordinada** en producción tras revisión/CI y autorización de cambios sobre permisos; primera validación sin datos de clientes.
8. Verificar funcionamiento de consultas, cambios pequeños y rechazos masivos, también después de reiniciar servicios.
9. Retirar la facultad de ejecutar SQL directo con credenciales privilegiadas, no solo ocultar binarios.

## Criterios de no despliegue
- Si `gpt-agent` sigue pudiendo usar `mariadb` con UPDATE/DELETE directos, SQL Guard NO se considera aplicado.
- Si el sistema de aprobación recibe la confirmación desde la misma IA, NO se considera aprobación independiente.
- Si solo hay pruebas SQLite, NO se considera probado MariaDB.
- No cambiar usuarios de las aplicaciones existentes.
- Ninguna actualización SQL real, eliminación, ALTER o corte de permisos sin copia verificada y prueba de rollback.

## Rollback
- Desactivar únicamente el servicio SQL Guard.
- Restaurar privilegios previos de la cuenta de agente desde un registro exacto de GRANT tomado antes de la operación, solo si el propietario autoriza devolver acceso directo temporal.
- Comprobar que las aplicaciones y las copias automáticas no se vieron afectadas.
