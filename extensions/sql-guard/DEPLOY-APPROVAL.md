# Instalación aislada del aprobador (plan de staging — NO desplegar en producción)

**Alcance actual:** sitio HTTPS y ceremonia de passkey; solicitudes autenticadas del agente; autorización firmada/efímera; comprobación de respaldo root-owned y pruebas de MariaDB. **No es un servicio de ejecución SQL**, y los permisos de `gpt-agent` siguen permitiendo UPDATE/DELETE directo. No declarar el sistema activo.

## Requisitos previos
1. GitHub PR revisado, CI verde y merge; desplegar solo un commit exacto, nunca editar archivos versionados en el VPS.
2. Dominio HTTPS elegido por el propietario y apuntando al VPS, certificado válido, firewall y Nginx que reenvíe `Host` al proceso local `127.0.0.1:8173`. No exponer Gunicorn al público.
3. Cuenta Linux independiente `sqlguard-approval`, sin sudo, sin home interactivo y sin acceso de escritura para `gpt-agent`.
4. Repositorio solo lectura en `/opt/sqlguard/current`, venv exclusivo `/opt/sqlguard/venv`, dependencias de `requirements-approval.txt`, unidad de referencia en `deploy/sqlguard-approval.service.example`.
5. Base SQLite de aprobaciones en `/var/lib/sqlguard/approvals.sqlite`, uid `sqlguard-approval`, modo 0600 y directorio 0700. Respaldo de esta base *sin secretos* en ruta separada.
6. Archivo `/etc/sqlguard/approval.env` propiedad root, 0600; nunca subirlo a GitHub ni mostrarlo en ChatGPT.

## Variables del servicio
```ini
SQLGUARD_DB_PATH=/var/lib/sqlguard/approvals.sqlite
SQLGUARD_RP_ID=approve.example.com
SQLGUARD_ORIGIN=https://approve.example.com
SQLGUARD_OWNER_ID=<id estable del propietario, configurado fuera del chat>
SQLGUARD_SIGN_KEY_HEX=<64 caracteres hex aleatorios, solo aprobación>
SQLGUARD_BOOTSTRAP_HASH=<sha256 del token de registro, secreto mostrado solo al propietario>
SQLGUARD_AGENT_TOKEN=<token aleatorio de 32+ caracteres, solo capacidad de crear solicitudes>
SQLGUARD_BACKUP_MANIFEST=/var/lib/sqlguard-trusted/manifest.json
SQLGUARD_BACKUP_DIRECTORY=/var/lib/sqlguard-trusted
```

El ejemplo `approve.example.com` **no es una URL configurada**. El origen debe ser exactamente el host con HTTPS: navegador, RP ID, cabecera Host y certificado deben coincidir. Registrar passkey exige un código de activación de un solo uso proporcionado localmente y luego un gesto de usuario en el teléfono.

## Respaldos de confianza
El aprobador solo aceptará un archivo `.sql.gz` y manifiesto `manifest.json` *propiedad root*, no editables por el agente ni por el usuario del aprobador. El manifiesto contiene `archive`, `sha256`, `created_at` (epoch UTC) y `databases`. Se comprueba checksum sobre el contenido real, integridad gzip, base solicitada y antigüedad máxima de 1h.

**Importante:** el backup de `gpt-agent` por sí solo no cumple esta garantía (escribible por el agente). Un proceso separado con privilegios root deberá crear y validar una copia congelada root-owned y publicar el manifiesto atómicamente. Sin ambos archivos válidos, la página rechaza toda autorización. No dar permisos de escritura del directorio trusted-backups a `sqlguard-approval` o `gpt-agent`.

## Operación
- Un cliente con `SQLGUARD_AGENT_TOKEN` puede proponer solicitudes mediante `POST /api/agent/stage` con operación estructurada y sha256 de respaldo; **no puede aprobarlas**. El servidor devuelve un enlace de caducidad corta.
- En la página `/approve/<id>` el propietario revisa la operación y firma una *challenge* WebAuthn usando la passkey registrada; ninguna contraseña, llave privada ni firma llega al chat.
- El servidor registra un comprobante firmado por operación exacta, respaldo, propietario y expiración; solo un consumidor confiable podrá consumir ese comprobante.
- El agente solo consulta `GET /api/agent/status/<id>` con su token. **El servicio actual todavía no ejecuta SQL.**

## Gates pendientes para activar producción
- Conexión autorizada de ChatGPT/connector al endpoint de propuestas (el agente no debe recibir claves de firma).
- Enrolamiento real de passkey del propietario, TLS válido y pruebas desde Android.
- Servicio de ejecución separado con conexión MariaDB de permisos mínimos; aprobación consumida atómicamente antes de cambios grandes y auditoría del resultado.
- Revisión de concurrencia, límite de solicitudes, tiempos de espera y plan de recuperación/rotación de passkeys.
- Verificación de que el agente pierde por completo los permisos directos de UPDATE/DELETE/ALTER/CREATE **después** de validar el ejecutor, conservando SELECT.
- Plan de rollback ensayado y continuidad de backups existentes.

**No habilitar, fusionar y desplegar por asumir que una batería de pruebas confirma la autenticación del usuario o el aislamiento del servidor real.**
