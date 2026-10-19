# VAST-004 — Autorizaciones de aprovisionamiento desde GPT Agent

La operación nueva `vast.provision` se prepara mediante el mismo
`hache-mining-operator.service` ejecutado como `hache-miner`. No se
conceden permisos SSH, sudo, SQL ni secretos al usuario `gpt-agent`.

## Modelo de operación

```json
{"method":"prepare","operation":{
  "action":"vast.provision",
  "instance_id":"123456",
  "release_commit":"40hexreemplazar",
  "step":"stage"
}}
```

Los pasos válidos son `stage`, `configure` y `apply`.
**Cada uno requiere una autorización root separada**, ligada al plan
íntegro y consumida antes del acceso SSH. `execute` es idempotente y
no envía una segunda llamada si el primer resultado es desconocido.
`prepare` no modifica instancias. Ningún paso arranca minería.

## Requisitos del VPS (administrativos; nunca desde gpt-agent)

Configurar para cada instancia `ID` los archivos privados:

- `/etc/hache-mining-operator/vast-provision/ID.json`:
  `instance_id` (texto), `machine_id`, `host_id`, `gpu_count`,
  `ssh_host`, `ssh_port`, `key_file`, `known_hosts`,
  `release_commit` y `archive_sha256`, con identidad fijada
  según Vast y commit integrado/verificado en GitHub.
- `/etc/hache-mining-operator/vast-provision/ID.private.json`:
  JSON con `recipe` validada y `ingest_key` admitida por el backend.
  Solo root y el servicio `hache-miner` pueden leerla, sin mostrarla
  en comandos de ChatGPT ni subirla a GitHub.
- `/etc/hache-mining-operator/ssh/ID.key` y
  `/etc/hache-mining-operator/ssh/ID.known_hosts`:
  clave dedicada cuyo *authorized_keys* remoto tiene forced-command,
  y huella de servidor confirmada por una fuente confiable, no por
  `ssh-keyscan` a ciegas.
- `/var/lib/hache-mining-operator/bundles/COMMIT40.tar.gz`:
  cuatro scripts de HACHE-MINER fijados por hashes Git y SHA-256. No
  usar `latest`, contenido sin revisar ni scripts dinámicos.

Usar directorios `root:hache-miner 0750`, archivos root:hache-miner
0640 donde el servicio debe leerlos. Revocar el acceso SSH root general
del agente que eluda el receptor remoto.

El ejecutor verifica de nuevo el inventario real Vast: ID, máquina,
host físico, GPU, relay SSH y estados `actual=intended=running`.
También exige `vast_leases.phase=armed`, que falten al menos 90 s
para stage/configure y 240 s para apply, y heartbeat del watchdog de
menos de 90 s. Cuando el alquiler esté detenido o haya caducado,
**falla cerrado**.

El envío SSH usa `BatchMode`, `StrictHostKeyChecking`,
`IdentitiesOnly` y `ClearAllForwardings`, con un único
`SSH_ORIGINAL_COMMAND` admisible. Los secretos viajan por stdin TLS
(no por argumentos/URLs, salida, PR ni logs); SSH cifra el transporte.

## Seguridad operacional y pasos pendientes

Para instalar el código productivo, primero fusionar y desplegar el
receptor en HACHE-MINER; después fusionar y desplegar el broker y helper
de Hache-Base. Crear las claves y política de host bajo autorización
administrativa, no por ChatGPT libre.

El broker actual procesa `execute` de manera síncrona y puede quedar
ocupado durante la instalación; el watchdog financiero es un temporizador
independiente. Una versión posterior debe usar una cola de trabajos
supervisada para progreso y recuperación.

Para certificar minería real falta una instancia nueva autorizada,
instalar la imagen con forced-command, probar handshake de identidad,
validar HMAC, muestras por GPU, shares Kryptex aceptados y límites de
coste. Estos pasos **no** se han probado en una instancia facturable.
No hay alquiler, compra, arranque o paro de instancias en estos PR.
