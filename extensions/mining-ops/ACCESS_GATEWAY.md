# Puerta operativa HACHE-MINER para ChatGPT

Entrada unificada **de solo lectura** a partir de componentes que ya funcionan en el
VPS. No instala un modelo, no crea un túnel TCP, no añade API pública, no da sudo,
no cambia los permisos SQL y no reemplaza a HACHE-MINER. Forma parte de Hache-Base
y se usa para HACHE-MINER, no para el portal Hache Natación.

## Comandos

Instalar `access_gateway.py` junto a `mining_status.py` desde un commit integrado
en un release inmutable bajo `/home/gpt-agent/mining-ops/releases/<sha>/`.
El enlace `current` debe apuntar a ese release, no a un archivo editado a mano.
Ejecutar desde Desktop Commander del dispositivo `gpt-agent`:

```sh
python3 /home/gpt-agent/mining-ops/current/access_gateway.py status
python3 /home/gpt-agent/mining-ops/current/access_gateway.py query vast.list
python3 /home/gpt-agent/mining-ops/current/access_gateway.py query vast.status --instance-id 56667162
python3 /home/gpt-agent/mining-ops/current/access_gateway.py query salad.targets
python3 /home/gpt-agent/mining-ops/current/access_gateway.py query salad.groups --organization hache --project prl-tests
python3 /home/gpt-agent/mining-ops/current/access_gateway.py query telemetry
```

- `status` ejecuta el diagnóstico acotado existente (MariaDB SELECT, systemd,
  cobertura y recursos); no implica que una instancia siga alquilada.
- `query` consulta el broker Unix ya instalado; las claves Vast y Salad siguen
  bajo la identidad `hache-miner`, nunca se entregan a `gpt-agent`.
- No hay acciones de escritura en la nueva interfaz. Las existentes `vast.stop`,
  `salad.stop` y `salad.reallocate` siguen exclusivamente en el broker con
  plan exacto y aprobación root independiente.

## SSH remoto opcional

La puerta admite **tres sondas fijas**, no un intérprete de comandos:
`gpu` (nvidia-smi), `miner` (cantidad de procesos SRBMiner) y `clock` (UTC).
Antes de conectar confirma en la API del proveedor que sea la MISMA instancia
y esté activa/lista. Si la API no confirma identidad, no abre SSH. El cliente
exige huella de host conocida y clave privada con permisos restrictivos:
`StrictHostKeyChecking=yes`, `BatchMode=yes` y sin forwarding.

El archivo **privado y NO versionado** de perfiles, para ejecutar en Linux con la
identidad que ya tenga las claves autorizadas, es
`~/.config/hminer-access/profiles.json`, modo 0600. Ejemplo de estructura
(sustituir host, puerto, huella conocida y rutas por datos verificables del
proveedor; estos valores ilustrativos NO sirven para conectar):

```json
{
  "profiles": {
    "vast-demo": {
      "provider": "vast",
      "instance_id": "12345",
      "host": "ssh.example.org",
      "port": 22001,
      "user": "root",
      "identity_file": "/home/gpt-agent/.ssh/id_ed25519",
      "known_hosts": "/home/gpt-agent/.ssh/known_hosts"
    },
    "salad-demo": {
      "provider": "salad",
      "instance_id": "instance-example",
      "organization": "hache",
      "project": "prl-tests",
      "group": "group-example",
      "host": "ssh.example.org",
      "port": 22022,
      "user": "root",
      "identity_file": "/home/gpt-agent/.ssh/id_ed25519",
      "known_hosts": "/home/gpt-agent/.ssh/known_hosts"
    }
  }
}
```

```sh
python3 /home/gpt-agent/mining-ops/current/access_gateway.py probe --profile vast-demo --test gpu
```

Las claves SSH, las huellas del host, el puerto/host y la autorización de acceso
a cada instancia deben existir **antes** de activar un perfil. Nunca asumir que
una clave de la laptop ya está disponible en el VPS; registrar únicamente la
clave pública de la identidad autorizada en el proveedor y comprobar huella
por canal de confianza. No habilitar `StrictHostKeyChecking=no`.
Una instancia detenida no da acceso SSH, aunque existan claves.

SaladCloud muestra las conexiones SSH por instancia en su Portal. Al recrearse
una instancia puede cambiar el host/puerto: verificar de nuevo su identidad y
huella y actualizar el archivo privado antes de sondear. No copiar claves
privadas de la laptop ni datos secretos de Salad a GitHub o al VPS.

## Límites operativos

Para ejecutar comandos de reparación, sincronizar artefactos, ejecutar
regresiones o modificar el minero en Vast/Salad, usar la conexión SSH
autorizada **mediante Desktop Commander del dispositivo apropiado**, solo
después de verificar la instancia, el commit de GitHub y el alcance de la acción.
La interfaz de sondas NO habilita ejecución shell arbitraria ni incorpora
autonomía de gasto. Las configuraciones del minero se versionan primero en
GitHub y se despliegan después de CI/revisión, sin editar código en los nodos.

La cuenta gpt-agent puede conservar privilegios directos de escritura MariaDB
hasta completar el cutover de SQLGuard. Esta puerta **no** es un sandbox SQL.
No ampliar esos privilegios ni hacer cambios a tablas fuera del procedimiento
versionado, con respaldo y aprobación independiente.

Si alguna conexión falla, indicar causa concreta: `provider_connection_unavailable`,
`profile_not_registered`, `vast_not_running_or_identity_changed`,
`salad_not_ready_or_identity_changed`, `ssh_probe_failed`, etc.
No sustituir la consulta real al proveedor por telemetría histórica.

### Verificación y reversión

`python3 -m unittest discover -s extensions/mining-ops -p 'test_*.py'`.

Smoke sin efectos: `status`, `vast.list`, `salad.targets`, `telemetry`.
Las sondas SSH requieren al menos una instancia corriendo, una clave pública
autorizada y huella verificada; no arrancar ni alquilar una instancia para
probarlas sin presupuesto autorizado.

Reversión: retirar el enlace al nuevo release y restaurar el anterior para
`gpt-agent`. No modificar el broker, servicios de minería, timers,
credenciales, instancias o SQLGuard.
