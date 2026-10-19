# Mining operator — órdenes bajo instrucciones del propietario

Servicio local del VPS que conecta la cuenta `gpt-agent` con las API de Vast y
Salad. No es una tarea programada ni un modelo autónomo. Reutiliza las credenciales
custodiadas por HACHE-MINER sin entregarlas al agente. No cambia el panel,
contraseñas, SQLGuard, mineros, temporizadores ni umbrales existentes.

## Capacidades de esta fase

- Lecturas: inventario y estado de Vast; búsqueda acotada de ofertas; proyectos,
  grupos e instancias de Salad; telemetría y cobertura registradas.
- Órdenes preparables: detener una instancia Vast registrada/habilitada,
  detener un grupo Salad de un proyecto habilitado o reasignar una instancia
  Salad individual que siga running/ready/started.
- Cada orden necesita una autorización root de un solo uso para el plan exacto,
  con identidad/estado actual y caducidad de cinco minutos. La instrucción del
  propietario debe existir antes de generar esa autorización; preparar un plan
  no autoriza ejecutarlo. La cuenta gpt-agent no puede generar autorizaciones.
- La reasignación respeta el lock, cooldown e intención de auditoría existentes
  de HACHE-MINER. No se crea un segundo motor automático.
- Contratar, iniciar, reiniciar, destruir, cambiar billetera o ejecutar SSH
  arbitrario **no están habilitados**. Aprovisionamiento/arranque requieren otra
  fase con presupuesto, ventana, parada efectiva y VAST-001 verificados.

## Uso desde el chat, mediante Desktop Commander del VPS

```sh
python3 /home/gpt-agent/mining-operator/client.py '{"method":"capabilities"}'
python3 /home/gpt-agent/mining-operator/client.py '{"method":"query","operation":{"action":"vast.list"}}'
python3 /home/gpt-agent/mining-operator/client.py '{"method":"query","operation":{"action":"salad.targets"}}'
```

Una orden se prepara con `method=prepare` y su `operation`. El resultado contiene
`plan_id`, `digest`, estado actual y caducidad. Antes de aplicar, el operador root
verifica que coincida con la instrucción humana y ejecuta:

```sh
python3 /opt/hache-mining-operator/current/authorize.py \
  --config /etc/hache-mining-operator/config.json \
  --plan-id <plan_id> --expected-digest <digest> --approve
```

Después, gpt-agent envía `{"method":"execute","plan_id":"..."}`. El mismo plan
no puede cambiar de operación ni destino. Repetir execute consulta el resultado
persistido, nunca vuelve a enviar la orden. `method=status` permite reconciliar
el estado. Una respuesta accepted/submitted **no acredita** que el proveedor haya
terminado: consultar su estado real y después telemetría/shares según corresponda.

Un timeout consume la autorización y queda como failed_or_unknown, sin reintento
automático. Antes de preparar otra solicitud consultar proveedor, auditoría y
cooldowns. No aprobar una parada/reasignación únicamente para probar el servicio.
Una prueba sobre un recurso que ya esté detenido debe verificar que no se envió
una mutación al proveedor.

## Transporte, secretos y límites

Socket Unix activado por systemd, grupo gpt-agent, modo 0660. El proceso verifica
SO_PEERCRED y solo acepta el UID configurado. No escucha TCP ni publica HTTP.
Los archivos de autorización son root, grupo hache-miner, 0640; su directorio es
root:hache-miner 0750. Se rechazan symlinks, hardlinks y archivos/directorios
modificables por el grupo u otros. Configuración y código del broker son root.

El servicio corre como hache-miner con memoria acotada. PHP carga el entorno
privado existente y usa claves Salad cifradas por organización. Para Vast usa
el archivo privado ya existente de control; si ese token carece de un permiso,
se devuelve el error seguro y no se amplían sus privilegios automáticamente.
No se devuelven tokens, variables de entorno, URLs de acceso ni logs libres.
Solo hay URLs fijas y proyecciones de campos explícitas.

Rate limit global persistente de 120 solicitudes por hora; JSON entrante de hasta
8 KiB; consultas/API acotadas. Inventarios truncados se marcan partial.
El origen SQL puede devolver datos viejos: el broker distingue telemetría de estado
actual del proveedor. Los errores 401/403/404/429 no se presentan como éxito.

## Instalación y reversión

Aplicar templates de deploy únicamente desde un commit integrado y comprobado.
Verificar UID real de gpt-agent, cuentas existentes, PHP curl/PDO y permisos.
Instalar release root en /opt/hache-mining-operator/releases/<commit>, enlace
current y configuración root protegida. Crear el directorio root de grants
antes de arrancar; StateDirectory de systemd crea el estado privado del servicio.
Instalar el cliente sin credenciales en el home de gpt-agent. Activar solo el
socket, no un timer; el primer comando inicia el servicio.

Smoke: capabilities, consultas reales, rechazos de otro UID, orden sin grant,
protección de claves y prueba de recuperación del servicio. Probar las órdenes
con mocks; ningún test debe interrumpir minería real. Mantener evidencia del
commit instalado y resultado observado por proveedor.

Reversión: detener/deshabilitar únicamente hache-mining-operator.socket/service.
No modificar los servicios de HACHE-MINER, Salad Monitor ni SQLGuard. Conservar
el estado de auditoría para reconciliar cualquier orden ya enviada.

Pruebas Linux:
`python3 -m unittest discover -s extensions/mining-operator -p 'test_*.py'`
y `php extensions/mining-operator/test_provider.php`.


## Extensión VAST-START-001 — arranque con fecha límite independiente

En GitHub, esta extensión prepara `vast.start`. **La acción no se habilita en
producción hasta instalar, ejecutar y comprobar el supervisor independiente
`hache-mining-operator-vast-lease.timer` y un release root integrado.**

Solicitud futura: `{"method":"prepare","operation":{"action":"vast.start",
"instance_id":"<ID>","max_hourly_usd":<tarifa máxima expresada por el propietario>,
"max_total_usd":<presupuesto autorizado>,"max_minutes":<duración autorizada>}}`.
No inventar los números ni reutilizar aprobaciones entre instancias. Para
ejecutar se necesita el mismo grant root exacto, caducidad y protocolo de
`authorize.py` ya implantados. Preparar no inicia ni factura GPU.

Condiciones del arranque: instancia **existente**, habilitada en HACHE-MINER,
actual=`exited`, intended=`stopped`, precio `dph_total` y hardware
válidos, enlace SSH publicado por Vast y coste estimado por duración dentro
del presupuesto. El supervisor corre como `hache-miner` cada 30 segundos,
independiente del broker y Desktop Commander. Mantiene una sola prueba con
gasto a la vez por seguridad. Antes de la llamada de inicio, el broker
comprueba timer activo y último ciclo correcto dentro de 90 segundos, y
registra en SQLite una obligación de parada duradera. Aunque el inicio
retorne timeout o el agente desaparezca, la obligación **no se borra**.
A partir del vencimiento el supervisor intenta detener la misma instancia,
comprobando `instance_id`, `machine_id` y `host_id`. Un HTTP de aceptación
no cierra la obligación; únicamente el estado real detenido.

**Importante:** el importe estimado NO constituye un tope bancario que Vast
garantice. La facturación puede seguir por almacenamiento, por retrasos de
API o si VPS/proveedor falla. Por tanto, no ofrecer una garantía absoluta
de gasto; mantener alertas financieras y verificar facturación.

Instalación administrativa desde una versión aprobada de GitHub:
1. Instalar release root completo en directorio inmutable; probar
   `test_broker.py`, `test_vast_start_guard.py`, `test_provider.php`.
2. Instalar `deploy/hache-mining-operator-vast-lease.{service,timer}.example`
   como unidades systemd, sin cambiar las de HACHE-MINER o Salad.
3. Activar timer y ejecutar **solo** la comprobación vacía del supervisor
   como `hache-miner` para crear heartbeat; comprobar `systemctl is-active`.
4. Consultar `capabilities` y preparar solicitudes ficticias de prueba
   sin crear autorización; `execute` sin grant debe fallar. Probar el
   vencimiento y errores de proveedor en mocks, nunca iniciando GPU reales.
5. Verificar toda regla de wallet, onstart, telemetría VAST-001/002 antes
   de autorizar cualquier ventana real. Para la instancia `56667162`,
   considerar el watchdog anterior, que puede detenerla inmediatamente
   si conserva un marcador histórico: reconciliar el estado antes del inicio.

Reversión: si no hay leases `armed`, restaurar release y desactivar el
nuevo timer. **Si existe un lease activo, mantener el timer y el código de
parada independientes hasta comprobar que la GPU quedó detenida.** No
revocar automáticamente una fecha límite al revertir el broker.

No hay credenciales de Vast en `gpt-agent` ni shell SSH arbitrario; el
intermediario sigue usando su API key privada.
