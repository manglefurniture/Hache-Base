# SQL Guard — aislamiento del ejecutor (preparación, NO desplegado)

Esta extensión implementa un servidor de socket Unix exclusivamente local en `runner_socket.py`; el agente manda una operación JSON tipada (no SQL) y opcionalmente un identificador de autorización. Las aprobaciones deben incluir `expected_rows` y `expected_primary_keys` (lista explícita de IDs), vinculados al hash firmado. El servicio funciona como `sqlguard-runner`, cuenta **diferente** de `gpt-agent`. Las credenciales de escritura jamás se entregan al agente.

## Política actual

- Consultas SELECT del agente: continuarían a través de su conexión MariaDB de lectura.
- UPDATE: se permite sin aprobación hasta **10 filas acumuladas por día UTC** a través del runner. El cupo persiste en SQLite y no se devuelve si una operación falla.
- DELETE: siempre requiere passkey y comprobación de respaldo, incluso para una sola fila.
- UPDATE de más de 10 filas: autorización autenticada y recuento exacto firmado y lista de claves primarias de 11 a 1000 registros.
- No se permite DROP, TRUNCATE, ALTER, INSERT, SQL arbitrario, condiciones vacías, columnas fuera de lista, ni modificar claves primarias por este servicio.
- Los cambios solo afectan claves primarias simples de tablas InnoDB configuradas, sin confiar en una segunda evaluación de un filtro amplio.
- Se rechaza si el recuento bloqueado difiere del recuento previamente aprobado. Si se consume un permiso y MariaDB da un error, queda marcado como gastado y no se reintenta automáticamente.

**Limitaciones importantes:** este mecanismo controla filas objetivo directamente modificadas; no prueba la ausencia de efectos indirectos por triggers, cascadas o procesos externos. Solo autorizar tablas y columnas tras auditar FK y triggers. El límite diario evita dividir un cambio masivo en numerosas peticiones pequeñas, aunque no sustituye auditoría y monitoreo.

## Aislamiento Linux y permisos (configuración futura con root)

Las cuentas se crearán sin shell y sin sudo:
- `sqlguard-approval`: interfaz HTTPS y claves WebAuthn, sin credenciales de MariaDB.
- `sqlguard-runner`: servidor Unix y credenciales de MariaDB con permisos UPDATE/DELETE solo en tablas autorizadas, sin permisos DDL o GRANT.
- `gpt-agent`: cliente del socket y consultas SQL read-only tras cutover, sin UPDATE/DELETE/ALTER/CREATE en producción.

Grupos aislados:
- `sqlguard-store`: `sqlguard-approval` y `sqlguard-runner`, **NO** `gpt-agent`.
- `sqlguard-callers`: `sqlguard-runner` y `gpt-agent`, **NO** la cuenta de aprobación.

Árbol de rutas previsto (aún no existe):
- `/var/lib/sqlguard`: `root:sqlguard-store`, modo `2770`. Base `approvals.sqlite` de grupo con escritura para ambos servicios, no para GPT.
- `/run/sqlguard`: `root:sqlguard-runner`, modo `0771` (ejecutor puede crear socket; otros solo atravesar).
- `/run/sqlguard/runner.sock`: socket con modo `0660` y grupo `sqlguard-callers`.
- `/etc/sqlguard/approval.env` y `/etc/sqlguard/runner.env`: archivos root 0600, secretos no versionados.
- `/etc/sqlguard/allowlist.json`: root 0644 o más restrictivo, columnas permitidas y sus claves primarias verificadas.

El socket también consulta las credenciales Linux del par (`SO_PEERCRED`) y rechaza usuarios distintos al UID autorizado de `gpt-agent`; nunca aceptar el UID del cliente como un parámetro HTTP.

## Variables adicionales del ejecutor

```ini
SQLGUARD_RUNNER_SOCKET=/run/sqlguard/runner.sock
SQLGUARD_RUNNER_ALLOWLIST=/etc/sqlguard/allowlist.json
SQLGUARD_RUNNER_DB_USER=sqlguard_runner
SQLGUARD_RUNNER_DB_PASSWORD=<secreto independiente del agente>
SQLGUARD_RUNNER_ALLOWED_AGENT_UID=<UID Linux verificado de gpt-agent>
SQLGUARD_RUNNER_SOCKET_GROUP_GID=<GID del grupo sqlguard-callers>
SQLGUARD_SIGN_KEY_HEX=<clave de verificación compartida solo por los dos servicios>
SQLGUARD_DB_PATH=/var/lib/sqlguard/approvals.sqlite
SQLGUARD_BACKUP_MANIFEST=/var/lib/sqlguard-trusted/manifest.json
SQLGUARD_BACKUP_DIRECTORY=/var/lib/sqlguard-trusted
```

La lista permitida es un JSON `{"schema":{"sandbox":{"items":["id","status"]}},"primary_keys":{"sandbox":{"items":"id"}}}`. El ejemplo **no se aplica a producción**. En despliegue, todas las tablas permitidas deben tener PK realmente verificada en InnoDB y no deben permitir efectos laterales inesperados.

## Conexión desde ChatGPT
Una vez instalado el servicio, Desktop Commander de `gpt-agent` puede enviar un único JSON al socket local; p.ej. `{"operation":{"database":"sandbox","table":"items","operation":"update","where":{"id":1},"values":{"status":"ok"}},"nonce":null}`. La respuesta será `{"ok":true,"affected_rows":1}` o un rechazo sin detalles secretos. Para una operación mayor, la interfaz ChatGPT ofrecerá primero el enlace HTTPS firmado con passkey, luego enviará al socket **la misma operación** con el nonce autorizado. Este flujo aún no se ha validado desde una conversación real.

## Verificaciones pendientes antes de producción

1. DNS y certificado TLS real para el dominio de aprobación; no hay un subdominio activo verificado.
2. Registro de passkey desde el dispositivo del propietario. Nunca introducir código de activación ni secretos en un chat.
3. Proceso root que cree un respaldo íntegro, manifiesto y checksum de propiedad root *antes* de cada aprobación; los respaldos actuales de gpt-agent son insuficientes para esta prueba de independencia.
4. Montar el directorio SQLite compartido con los permisos precisos; probar el socket entre identidades Linux reales, y rechazos desde otros UID.
5. Instalar ambos servicios **solo desde un commit integrado en GitHub**, con venv separado.
6. Verificar transacciones y cascadas en un entorno aislado con el mismo esquema que producción.
7. Probar aprobación WebAuthn verdadera, cierre de sesión, caducidad, duplicados, pérdida de conectividad y recuperación.
8. Verificar respaldo y plan de rollback; después revocar privilegios directos de escritura de `gpt-agent` sin alterar usuarios de las aplicaciones.
9. No activar mientras queden vías de conexión directa con escritura o cuentas privilegiadas accesibles al agente.

**Ninguno de estos cambios de cuentas, grupos, DNS, privilegios o servicios fue ejecutado en el VPS.**
