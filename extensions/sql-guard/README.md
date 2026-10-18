# SQL Guard — política preliminar (NO desplegar)

Extensión opt-in inspirada en el modelo de seguridad de Hache-Base.

## Garantías actuales
- `policy.py` **solo evalúa decisiones sobre peticiones estructuradas**.
- Deniega operaciones desconocidas, bases fuera de lista y escrituras sin recuento confiable.
- Exige aprobación verificable y respaldo previo para operaciones masivas (>10 registros por defecto) o destructivas.
- Contiene pruebas unitarias sin conexión a datos reales.

## Límites críticos
**Esto no protege producción por sí solo.** La cuenta Linux `gpt-agent` dispone actualmente de acceso SQL directo a cinco bases y conserva UPDATE/DELETE/ALTER. Puede saltarse completamente esta política mediante el cliente MariaDB. No utilizar esta librería como sustituto de permisos.

Antes de desplegar un ejecutor:
1. Implementar un servicio de ejecución separado, con cuenta Linux y credenciales de BD distintas; `gpt-agent` solo puede solicitar operaciones.
2. Revocar UPDATE/DELETE/ALTER directos de `gpt-agent` después de probar el servicio, siguiendo una ventana coordinada y plan de rollback. En caso de no poder revocar, **no declarar la protección activa**.
3. Jamás ejecutar SQL generado libremente; permitir operaciones tipadas y SQL parametrizado con listas de tablas/columnas permitidas. Validar SQL con parser apropiado si se expone SQL arbitrario, no expresiones regulares.
4. Calcular filas afectadas dentro de la misma transacción bajo bloqueo adecuado; no confiar en un recuento aportado por la IA.
5. Registrar approvals de un canal humano autenticado, con identidad, caducidad, nonce de un solo uso y hash de operación; `approved` no debe provenir de entrada del agente.
6. Respaldar, comprobar SHA256 y, para operaciones irreversibles, restaurar en entorno aislado antes de ejecutar. La confirmación humana no sustituye un backup.
7. Auditoría append-only en ubicación inaccesible para la cuenta que invoca, pruebas de concurrencia, rollback, doble envío y denegación por defecto.
8. Desplegar desde GitHub con checks, revisión, merge y verificación; nunca editar código versionado en el VPS.

## Ejecutor experimental

`executor.py` implementa un ejecutor limitado para pruebas SQLite (UPDATE/DELETE por igualdad, lista explícita de identificadores, conteo transaccional). **No está preparado para MariaDB ni producción**: usa `BEGIN IMMEDIATE` de SQLite y requiere aislamiento de credenciales, mecanismo autenticado de aprobación, auditoría y pruebas específicas de concurrencia en MariaDB. La ejecución masiva se rechaza incluso si se aporta una aprobación; esa capacidad todavía no está construida.

## Probar sin dependencias externas

`cd extensions/sql-guard && python3 -m unittest discover -v -p 'test_*.py'`

No habilitar en aplicaciones ni modificar permisos MariaDB como parte de este PR.

## Aprobación elegida: desde ChatGPT
La interfaz conversacional puede presentar la solicitud y los detalles, pero **una respuesta de texto «sí» no constituye autorización autenticada del servidor**.

El componente `approval.py` verifica un comprobante criptográfico con:
- hash canónico de la operación exacta;
- identidad del aprobador verificada por un servicio independiente;
- vencimiento máximo de cinco minutos;
- nonce de un solo uso, consumido de forma atómica por un almacén persistente;
- referencia a respaldo verificado;
- firma HMAC con secreto custodio del servidor de aprobaciones, no accesible al agente.

**Implementado únicamente en código experimental:** página web independiente con ceremonias WebAuthn, almacenamiento de credenciales y desafíos, emisión de comprobantes firmados, vencimiento y anti-replay. Incluye verificador de respaldo root-owned, rechaza autorizaciones si este no se configura, y pruebas automatizadas. **Aún no está desplegado ni registrado ningún dispositivo.** La identidad del chat nunca se equipara a identidad autenticada. Falta conectar a ChatGPT el enlace real, ejecutar un enrolamiento WebAuthn real del propietario, instalar el runner SQL aislado, auditar límites y retirar después los privilegios directos. No insertar claves HMAC en prompts, logs, repositorios ni credenciales de `gpt-agent`.

Ver `DEPLOY-APPROVAL.md` y `CHATGPT-APPROVAL-CONTRACT.md` antes de cualquier puesta en marcha.

## Estado del runner aislado — implementación de laboratorio

`runner_socket.py` añade un canal local Unix para que `gpt-agent` envíe peticiones estructuradas al servicio `sqlguard-runner` **sin conocer las credenciales SQL**. El socket comprueba el UID Linux del cliente, ACL de grupo y límite estricto de tamaño; no admite SQL libre.

`authorized_runner.py` aplica la política actual:
- Todos los `DELETE` requieren passkey, comprobante firmado de un solo uso, respaldo independiente y recuento exacto.
- Un `UPDATE` sin aprobación queda limitado a 10 filas por petición **y 10 filas acumuladas por día UTC** en todas las bases; el cupo está protegido en el almacén SQLite del servicio.
- Los `UPDATE` aprobados permiten entre 11 y 1000 filas, nunca más, si el recuento bloqueado coincide exactamente con el recuento aprobado.
- Se rechazan siempre las condiciones vacías y los cambios fuera de lista; los comandos DDL no están implementados.
- El mecanismo prueba las filas directamente modificadas; los efectos indirectos de triggers/cascadas deben auditarse por separado.

`deploy/create-trusted-backup.sh.example` genera un dump y un manifiesto verificable root-owned dentro de `/var/lib/sqlguard-trusted`, ruta separada de cualquier directorio que el servicio de aprobaciones pueda modificar. La plantilla no se ejecutó ni programó en producción.

**La separación de identidades está preparada en código y documentación, no desplegada.** `gpt-agent` todavía tiene acceso directo de escritura a las cinco bases: sigue existiendo el bypass hasta la transición de permisos.

Ver también `DEPLOY-RUNNER.md` y `DEPLOY-APPROVAL.md`.
