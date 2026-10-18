# SQL Guard — primer respaldo de confianza (sin purga automática)

La copia inicial es **de solo lectura hacia MariaDB** y crea archivos
nuevos en \`/var/lib/sqlguard-trusted\` como root. No reemplaza las copias
automáticas actuales ni valida por sí misma una restauración.

## Condiciones previas
- Código revisado, CI verde y merge en GitHub.
- Ejecutar el archivo exacto \`create-trusted-backup.sh.example\` desde el
  commit fusionado, previa verificación del hash.
- Una sesión root humana (ConnectBot), no \`gpt-agent\` ni \`deploy-hache\`.
- MariaDB estable y al menos 4 GiB libres en el filesystem.
- Directorio \`/var/lib/sqlguard-trusted\`: \`root:sqlguard-store\`,
  0750, sin symlinks ni escritura por servicios o agentes.
- Evitar DDL y migraciones mientras transcurre el backup.

## Garantías y alcance
El script verifica identidad root, permisos y espacio, obtiene \`flock\`,
y ejecuta \`mariadb-dump --no-defaults --user=root --socket=/run/mysqld/mysqld.sock\`
por la conexión Unix root, sin cargar opciones heredadas de cliente, con
\`--single-transaction --quick --routines --events
--triggers\` para \`hache_natacion\`, \`hache_miner\`, \`hache_tienda\`,
\`nova_boutique\` y \`solution_spa\`. Bajo Bash \`pipefail\`, un error de
MariaDB o gzip impide publicar el resultado.

Comprueba gzip, calcula SHA-256 y publica primero el archivo y luego el
manifiesto atómicamente. Ambos son \`root:sqlguard-store\`, 0640. La salida
solo incluye nombre y checksum, sin datos ni contraseñas.

**No se borran respaldos anteriores.** Definir retención y periodicidad
requiere otra implementación revisada.

## Requisitos posteriores
1. Verificar manifiesto y archivo en root, checksum y cinco bases.
2. Ejecutar la función versionada \`verify_backup\` como
   \`sqlguard-approval\`, sin transmitir archivos al agente.
3. Ensayar restauración en instancia aislada, sin \`DROP\` ni importación
   en bases vivas.
4. Confirmar denegación de acceso a \`gpt-agent\`.
5. Toda aprobación requiere backup válido de menos de una hora: de lo
   contrario se rechaza hasta contar con otra copia reciente.

No inicia servicios de SQL Guard, no cambia permisos MariaDB ni expone
la interfaz HTTPS de aprobaciones.
