# GPT Agent — acceso independiente de laptop a Vast y Salad

Objetivo: operar desde ChatGPT a través del dispositivo Desktop Commander del VPS
(identidad `gpt-agent`), **incluso con la laptop Hache apagada**. El VPS no
ejecuta un modelo de IA; es una puerta de acceso autenticada a herramientas.

## Estado de esta fase

- VPS/MariaDB y API Vast/Salad: operativos a través del broker local existente.
- Nuevo contrato `vast.status`: devuelve exclusivamente la dirección `ssh_host`
  y el puerto `ssh_port` publicados por la API autenticada, además de ID de
  instancia, máquina, host físico y GPU. No devuelve claves ni tokens.
- `register-vast`: registra sin arrancar la instancia un perfil privado ligado
  a **instancia + máquina física + host físico + 1–16 GPU + relay SSH**.
  No reemplaza perfiles existentes ni usa host/puerto inventados.
- `probe`: antes de conectar debe confirmar estado `running` y que todos
  esos datos siguen coincidiendo. `StrictHostKeyChecking=yes`: nunca autoacepta
  una huella nueva; si cambió la dirección o el hardware aborta.
- Salad: consultas API disponibles; **SSH desde el gateway permanece
  intencionalmente bloqueado** hasta que el proveedor proporcione una asociación
  verificable de identidad → dirección/puerto SSH. No confiar en un IP manual.
- Arrancar/detener/alquilar mineros **no se habilita** en este cambio. La
  autorización para desarrollar no permite costes ni interrupciones.

## Pasos para el despliegue sin gasto

1. Esperar CI, revisión y merge en GitHub. **El archivo PHP del operador root
   necesita actualización desde un release integrado**. No editar
   `/opt/hache-mining-operator/current/provider.php` manualmente. El usuario
   `deploy-hache` carece del permiso sudo necesario para reemplazar ese
   servicio root; usar el proceso de instalación administrado ya aprobado
   por el propietario, sin ampliar permisos.
2. Desplegar el nuevo `access_gateway.py` en el release inmutable de
   `/home/gpt-agent/mining-ops/releases/<commit>`, comprobar Git blob hashes
   y mover `current` de forma atómica con posibilidad de rollback.
3. Comprobar como gpt-agent:
   ```sh
   python3 /home/gpt-agent/mining-ops/current/access_gateway.py query vast.status --instance-id 56667162
   python3 /home/gpt-agent/mining-ops/current/access_gateway.py register-vast --instance-id 56667162
   ```
   El segundo comando solo crea `~/.config/hminer-access/profiles.json`,
   protegido 0600, y valida la clave privada preexistente 0600 de
   `gpt-agent`. Se puede ejecutar con una instancia detenida. Si el broker
   todavía no entrega host/puerto, responde con error y NO crea el perfil.
4. Verificar por un canal confiable la **huella pública SSH del relay actual**.
   Registrar el host key validado en
   `/home/gpt-agent/.ssh/known_hosts`. No basta con aceptar automáticamente
   el resultado de `ssh-keyscan`. No copiar claves privadas de la laptop.
5. **Registro de la clave pública de gpt-agent ante Vast**: efectuarlo solo
   con autorización explícita para esa vinculación, limitando destino y
   credenciales. Una clave privada existente no garantiza acceso si su clave
   pública no está registrada. La instancia detenida NO puede utilizar SSH.
6. En una futura ventana explícitamente autorizada para gastar, validar
   `probe --profile vast-56667162 --test gpu` y `--test miner` después de
   arrancar mediante el mecanismo controlado aprobado. Confirmar 8 GPU
   físicas y validar hashrate/shares con telemetría y pool. Ni un proceso
   activo ni nvidia-smi demuestran un hashrate de 400 TH/s por GPU.

## Acciones futuras bajo permiso específico

El `gpt-agent` debe poder solicitar preparación de orden, autorización exacta
con caducidad y ejecución auditada. Para `vast.start`, antes de habilitar la
escritura API se necesita un tope vinculante de gasto y duración, parada
independiente de fallos del agente, revisión de tarifa real, confirmación de
billetera/workers y recuperación al apagar (VAST-001/002). No añadir sudo
general, credenciales del proveedor en la cuenta gpt-agent ni TCP público.

Para Salad: implementar un lector de conexión SSH que devuelva solo metadatos
de instancia firmemente vinculados a su ID y a su estado. Cada nueva réplica
podría obtener host y puerto distintos. Dejar el acceso bloqueado hasta que
esa verificación y sus pruebas existan.

## Seguridad y reversión

Cualquier cambio inesperado en ID, GPU, máquina, relay SSH, huella de host
o precio requiere una nueva verificación. Rollback del release del cliente a
la versión anterior; del operador root al release anterior, conservando los
archivos privados y auditoría. No tocar MariaDB, producción ni instancias en
la preparación del acceso.
