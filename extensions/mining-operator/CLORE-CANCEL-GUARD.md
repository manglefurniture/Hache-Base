## Bloqueo de seguridad de divisas (octubre 2026)

La documentación pública de Clore describe pagos de alquiler en **Bitcoin o CLORE**
y la facturación en USD como una función pendiente. Los campos de
`my_orders` (`price`, `spend`, `creation_fee`) se expresan en la
**moneda nativa de la orden**, no necesariamente en USD. Por tanto, calcular
un corte como si esos importes fueran dólares sería inseguro.

Antes de registrar una orden, el código exige una consulta privada
autenticada de `my_orders` y valida exactamente ID, servidor, momento,
modalidad Spot, estado no vencido, moneda USD, precio, comisión y cargo fijo.
Una orden `bitcoin`, `clore`, de moneda omitida o distinta de USD se
**rechaza**. Si una obligación previamente armada presenta después
moneda o comisión incompatible, el guard solicita cancelación temprana y
no marca cierre hasta `expired: true`.

Esto **no quiere decir que Clore admita actualmente alquileres en USD**.
En la práctica, las rentas nuevas seguirán bloqueadas hasta desarrollar y
verificar contabilización independiente en moneda nativa, cambio a USD
actualizado, costes totales, ventana previa al `create_order` y autorización
unívoca. El supervisor instalable puede permanecer activo **sin órdenes**
para comprobar conexión, permisos y heartbeat; nunca basta por sí solo
para autorizar un gasto.

## Instalador revisado, sin nuevas rentas

Después de fusionar un PR, desplegar el **SHA completo** mediante la puerta
existente (con comprobación previa/posterior de obligaciones Clore y Vast).
Sólo luego un administrador root puede instalar el temporizador usando
`deploy/install-clore-cancel-guard.sh <SHA> /etc/RUTA_DE_CREDENCIAL_PRIVADA`.
El segundo argumento es una **ruta**, no el token. La ruta debe señalar
un archivo real no enlazado, root:root y modo 0600; el instalador no copia,
imprime ni expone el secreto. Aborta si el archivo no existe, si hay otro
servicio Clore o base SQLite previa, si el código no corresponde al SHA
activo, si faltan supervisores o si falla el test. Sólo realiza el primer
`GET my_orders` autenticado, nunca crea ni cancela alquileres al instalarse.

El repositorio no contiene la credencial. No adivinar su ubicación ni
copiarla a `gpt-agent` ni a Telegram. La instalación exige constatar en
root dónde está custodiada, sin pegarla en una conversación.


# Clore Spot: corte financiero independiente (fase de seguridad, sin rentas)

**Estado:** implementación propuesta por PR. No habilita `create_order`, pujas ni
`clore.cancel` en el broker. No debe utilizarse para justificar un alquiler
hasta cerrar los prerrequisitos de integración.

## API oficial (octubre 2026)
- `GET /v1/my_orders?return_completed=true` con cabecera privada `auth`.
- `POST /v1/cancel_order`, JSON `{"id":<order_id>}`.
- `code=0` del POST = aceptación; **no** certifica la detención.
- Solo `expired: true` para **ese order_id** en `my_orders` cierra la obligación.
- Hay límite global de ~1 solicitud/s por cuenta; el watchdog pausa 1.1 s
  entre lectura y cancelación. No recuperar la clave para el agente.

## Funcionamiento

`clore_cancel_guard.py` es independiente de la conexión del chat y del broker.
Una tabla SQLite duradera conserva: ID exacto de **orden** (no ID de servidor),
servidor previsto, tarifa Spot diaria en USD-Blockchain, presupuesto autorizado,
fecha de creación, comisión fija de creación, límite temporal, corte efectivo, última tentativa y cierre
confirmado.

El supervisor se ejecuta cada 30 s por `systemd`. Si la fecha límite llegó:
1. Consulta órdenes del proveedor. Si ya consta `expired: true`, cierra.
2. Si está activa, falta del historial o la consulta falla: solicita cancelación
   por ID. Ninguna pérdida de conexión se trata como cancelación confirmada.
3. Mantiene la obligación `armed` después de una respuesta `code=0`.
4. Vuelve a consultar y reintenta hasta verificar `expired: true`.
5. Ante ID ligado a **otro servidor** se niega a cancelar y registra anomalía
   para intervención humana, sin afirmar cierre.

El corte se calcula desde la **fecha real de creación de la orden**, el menor de:
- duración explícitamente autorizada, o
- instante al que el precio diario aprobado (+5% de gastos estimados)
  consumiría 85% del presupuesto **restante tras descontar la comisión fija
  de creación real**. Exige al menos 90 segundos entre registro y corte.
- si Clore reporta tarifa superior a la puja autorizada, o un cargo diario
  adicional de overclock, dispara cancelación anticipada.

Es un **corte preventivo estimado**, NO un límite de gasto garantizado por Clore.
Tarifas, comisiones, rezago de red, precio real de puja o caída de API/VPS pueden
hacer que se supere el límite. Requiere revisión de facturas y alertas independientes.

## Despliegue seguro (NO ejecutado por este PR)

1. Integrar PR únicamente con CI verde y revisión. Copiar release de GitHub
   a `/opt/hache-mining-operator/releases/<SHA>`; no editar código versionado
   directamente en el VPS.
2. Confirmar dónde está custodiada **realmente** la clave de Clore. Ajustar el
   `LoadCredential=clore_key:` del ejemplo exclusivamente por deploy versionado;
   NO imprimir, mover a home de gpt-agent, ni aumentar permisos.
3. Instalar dos unidades `deploy/hache-mining-operator-clore-cancel.*.example`
   como `hache-mining-operator-clore-cancel.{service,timer}`. Mantener intactos
   los timers de Vast, Salad y SQLGuard; proteger
   `/var/lib/hache-mining-operator` para usuario `hache-miner`.
4. Activar timer y ejecutar un tick vacío; deberá consultar autenticadamente
   `my_orders` y guardar heartbeat reciente en SQLite. Sin token o conexión el
   timer falla y **no** permite registrar alquileres.
5. Comprobar `systemctl is-active hache-mining-operator-clore-cancel.timer`,
   `journalctl -u hache-mining-operator-clore-cancel.service` (sin secretos),
   y `clore_cancel_guard.py status`.

Registro de una orden **ya existente** en un procedimiento administrativo:
```sh
# Únicamente root, y sólo tras autorización explícita del propietario.
# Valores ilustrativos; NO ejecutar con ellos.
python3 /opt/hache-mining-operator/current/clore_cancel_guard.py arm \
 --approved --order-id ORDER_ID --server-id SERVER_ID \
 --daily-bid-usd DAILY_USD --budget-usd MAX_TOTAL_USD \
 --creation-fee-usd ACTUAL_FEE_USD \
 --max-minutes MAX_MINUTES --created-unix PROVIDER_CREATED_EPOCH
```
`arm` exige root, timer activo, heartbeat reciente, una sola orden armada,
fecha válida, comisión fija real y al menos 90 segundos antes del vencimiento.

**Límite crítico para alquiler futuro:** `arm` acepta una orden ya existente.
Esto **no elimina** la ventana entre `create_order` y `arm`. Antes de activar
el alquiler automatizado es obligatorio incorporar al mismo flujo autorizado:
reserva duradera de presupuesto **antes** de crear, inventario base de órdenes,
reconciliación inequívoca del order_id (aun con timeout del POST),
vinculación/cancelación automática desde el supervisor, y prueba del watchdog
con el orden exacto sin costo. Hasta entonces, NO autorizar una prueba pagada
por considerarlo un hard cap.

## Pruebas sin gasto
```sh
python3 -m unittest discover -s extensions/mining-operator -p 'test_clore_cancel_guard.py' -v
python3 -m py_compile extensions/mining-operator/clore_cancel_guard.py
```
Pruebas: sin POST antes del límite; reloj/presupuesto; éxito del POST no cierra;
confirmación independiente; reintento tras 429/timeout; lectura fallida en el
vencimiento; servidor equivocado; órdenes ausentes; credenciales; rechazo sin
timer/heartbeat. Todas usan objetos simulados, no API real.

**Reversión:** nunca desactivar el timer si SQLite todavía contiene leases
`armed`. Mantener supervisor y credencial protegidos hasta confirmación
`expired: true`. Si no hay leases activos, desactivar el timer y restaurar
release anterior desde GitHub.
