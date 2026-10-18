# SQL Guard — inicialización aislada del almacén de aprobaciones

Una vez creados los secretos locales y verificada la instalación Python,
el propietario puede ejecutar \`prepare-approval-store.sh\` **como root desde
ConnectBot**, usando el archivo de un commit **fusionado y comprobado contra
su blob GitHub**.

## Alcance seguro

\`--check\` (predeterminado):
- exige root para inspeccionar \`/etc/sqlguard/approval.env\` y
  \`/root/sqlguard-enrollment-token\` **solo por metadatos**, sin mostrar valores;
- verifica que ambos sean archivos root:root 0600, no symlinks y no vacíos;
- confirma que ambas unidades de SQL Guard estén inactivas y deshabilitadas;
- comprueba las identidades y pertenencias de grupo y el directorio compartido.

\`--init-store\` realiza lo anterior y, si el almacén no existe:
- inicializa el esquema versionado SQLite como \`sqlguard-approval\` mediante
  el intérprete de \`/opt/sqlguard/venv\` con umask 0007;
- confirma propiedad \`sqlguard-approval:sqlguard-store\`, modo 0660;
- prueba apertura SQLite y esquema mediante \`sqlguard-runner\` y rechazo de
  apertura por \`gpt-agent\`.
- no necesita cargar ni transmitir a través de argumentos los secretos.

La inicialización usa claves de construcción efímeras no persistentes: el
esquema SQLite no almacena la clave HMAC ni el owner ID al crear tablas; la
clave real solo se cargará por systemd en el servicio aislado cuando se
autorice su activación local.

**No** modifica Nginx, servicios, usuarios MariaDB ni otros repositorios,
ni crea respaldos de producción. El sitio HTTPS seguirá en 503.

## Barreras de activación posteriores

Se requieren copia de respaldo root-owned comprobada, un ensayo de
restauración, pruebas de rechazo por UID y acceso al socket, revisión de
exposición web y registro WebAuthn real por el propietario. No se iniciará
el runner ni se reducirán los permisos directos MariaDB de \`gpt-agent\`
antes de terminar las verificaciones y acordar la transición.
