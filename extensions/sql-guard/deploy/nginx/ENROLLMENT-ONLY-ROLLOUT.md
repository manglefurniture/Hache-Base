# SQL Guard — publicación temporal para alta de la passkey

Este despliegue **NO** habilita la autorización de operaciones SQL desde
ChatGPT. Publica únicamente el registro inicial WebAuthn por HTTPS. No crea
cuentas root, no cambia MariaDB, no expone el servicio Gunicorn fuera de
127.0.0.1 ni permite solicitudes o aprobaciones públicas.

## Validaciones previas (solo lectura)

1. Fusionar el PR y registrar el commit y el hash SHA-256 exactos.
2. Verificar que \`sqlguard-approval.service\` está activo, deshabilitado
   al arranque, escuchando solo \`127.0.0.1:8173\`, sin reinicios/OOM y con
   límites de memoria.
3. Comprobar \`GET /enroll\` local con \`Host:
   aprobaciones.hacheinteractive.com\` devuelve 200, y \`POST
   /api/agent/stage\` sin token devuelve 401.
4. El certificado HTTPS debe ser válido y el sitio público seguir en 503.
5. No leer ni mostrar \`/etc/sqlguard/approval.env\` ni el token de registro
   desde herramientas conectadas a ChatGPT. Cuentas privadas y respaldos
   permanecen inaccesibles a \`gpt-agent\`.

## Activación reversible por root del propietario

- Preservar la configuración anterior en \`/root/sqlguard-prep\`.
- Transferir la configuración de este repositorio desde commit fusionado,
  verificar su SHA-256 y permisos \`root:root\` 0644.
- Usar \`nginx -t\` **antes** de recargar; si falla, restaurar la configuración
  anterior sin recargar y abortar.
- Recargar Nginx sin reiniciar los otros vhosts. Verificar certificados y
  resultado de ruta desde **fuera del servidor**, además de localmente.
- Comprobar que GET \`/enroll\`, \`/static/approval.css\` y
  \`/static/approval.js\` sirven 200. Confirmar que
  \`/api/agent/stage\`, \`/api/agent/status/\`, \`/api/approve/\`,
  \`/approve/\` y cualquier ruta no allowlisted devuelven 503.
- Solo \`POST /api/enroll/start\` y \`/api/enroll/finish\` pasan al backend,
  con límites por IP. El backend valida el origen HTTPS y el código de alta.
- **Si falla alguna verificación, restaurar el archivo de Nginx, ejecutar
  \`nginx -t\` y recargar.**

## Alta desde Android

1. Abrir \`https://aprobaciones.hacheinteractive.com/enroll\` en Chrome
   normal, no en el navegador incrustado de otra aplicación.
2. Consultar personalmente el código de alta desde una **consola root local**
   en ConnectBot. Introducirlo en el formulario del sitio HTTPS. No publicarlo
   en GitHub, ChatGPT, logs, capturas ni notas compartidas.
3. Presionar \`Registrar passkey\` y completar el diálogo nativo de Android
   con la opción de gestor de llaves aprobada.
4. Confirmar \`Passkey registrada.\` en el teléfono. Si falla, no reintentar
   sin verificar la causa (hasta tres ceremonias simultáneas).
5. Comprobar en la sesión root que el almacén contiene exactamente un
   identificador de passkey; **solo imprimir COUNT(*)**, jamás la clave
   pública, token de alta, datos de autenticación ni challenge.

Después del enrolamiento se debe volver al placeholder HTTP 503 de inmediato,
sin eliminar la passkey del almacén. La exposición posterior para aprobar
operaciones será otro PR y otro paso de autorización.

## Importante

La copia validada del respaldo envejece: su comprobación de menos de una hora
solo habilita futuras autorizaciones mientras sea reciente. El alta de passkey
es independiente de esa frescura y **no autoriza** cambios SQL directos ni
revocación de privilegios actuales.
