# SQL Guard — preparación de credenciales del aprobador (solo staging)

**No habilitar Nginx ni iniciar unidades antes de comprobar identidad, backups,
permisos y retorno a estado anterior.** Este paso prepara exclusivamente el
entorno secreto local de la aprobación; no configura el ejecutor SQL.

## Requisitos

- El código SQL Guard está instalado desde un commit integrado bajo
  \`/opt/sqlguard/current\` y es propiedad de root, sin escritura por grupo/otros.
- \`python3.13-venv\` y dependencias en \`/opt/sqlguard/venv\` instaladas.
- Las cuentas y grupos independientes ya existen.
- \`/etc/sqlguard\` y \`/root\` son directorios root-only.
- \`aprobaciones.hacheinteractive.com\` sigue en HTTPS con respuesta 503.

## Script de solo privilegio administrativo

\`prepare-approval-credentials.py\` se importa de un **commit de GitHub revisado
y fusionado**. Antes de ejecutarlo, verificar SHA Git del archivo transferido.
El modo por defecto \`--check\` no realiza modificaciones. El modo \`--apply\`
solo permite root y falla si existe cualquiera de los destinos:

- \`/etc/sqlguard/approval.env\` (root:root, 0600; cargado únicamente por systemd)
- \`/root/sqlguard-enrollment-token\` (root:root, 0600; código de alta humano)

Se generan en el servidor con \`secrets\`: un identificador estable aleatorio
de propietario, una clave de firma HMAC de 256 bits, un bearer token de agente,
y un código de enrolamiento. **El token de registro nunca aparece en la salida,
los logs de servicios, el chat ni el repositorio**. El archivo del código permite
mostrarlo únicamente en la terminal root del propietario al registrar su passkey
desde Android. Nunca enviar capturas o el valor a ChatGPT.

El script incluye el origen y RP ID exactos
\`https://aprobaciones.hacheinteractive.com\`, y los paths al respaldo
\`/var/lib/sqlguard-trusted\`. Hasta tener una copia root-owned verificada,
cualquier autorización de cambios SQL debe fallar.

## Próximos pasos, independientes y reversibles

1. Preparar almacén SQLite compartido, permisos cross-UID y backup verificado.
2. Con el servicio de aprobación **solo en 127.0.0.1**, probar arranque,
   reinicio, errores esperados, límites y ausencia de secretos en logs.
3. Solo después de verificar TLS, aislamiento y usuario real, habilitar de
   forma controlada el proxy HTTPS para el enrolamiento WebAuthn.
4. La credencial del agente no se concede a \`gpt-agent\` hasta existir un
   intermediario seguro. El token **no concede capacidad de aprobar**.
5. El runner y el broker administrativo privilegiado se prueban en sandbox;
   no reducir permisos SQL directos hasta superar pruebas y rollback.

El modo de instalación no crea servicios, no modifica sudoers ni base de datos,
ni hace peticiones HTTP ni activa el sitio de aprobaciones.
