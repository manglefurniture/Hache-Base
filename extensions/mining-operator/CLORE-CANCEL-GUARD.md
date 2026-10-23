## Recuperación independiente de órdenes inciertas (fase de seguridad)

El watchdog ahora inspecciona en cada ciclo los prealquileres de SQLite con
`phase=uncertain` y `outcome=create_submitted_once` o
`create_response_unknown`. Estas marcas **no se generan por este PR**:
requieren un futuro ejecutor con autorización criptográfica de una oferta
específica y registro duradero anterior al único POST `create_order`.

Consulta exclusivamente `my_orders?return_completed=true`. Compara el
inventario posterior con el baseline guardado y verifica identidad exacta
de servidor, imagen Docker, GPU, moneda `USD-Blockchain`, fecha y costes.
Un cambio en **cualquier otro servidor** se trata como actividad ajena,
nunca como evidencia concluyente de nuestro alquiler.

La tabla `clore_pending_recovery` conserva `checked_at`, clasificación
y posible ID candidato, sin guardar credenciales. Aun ante una coincidencia
única, no vincula la orden ni envía `cancel_order`: el ID es **candidato**,
no una prueba del origen de la orden. El servicio falla con
`possible_unprotected_clore_order`, dejando una evidencia visible en
`clore_cancel_guard.py status`. Los fallos de red no refrescan el
heartbeat ni desbloquean reservas.

Es una medida de **detección y bloqueo**, no una protección financiera
completa. Ante una respuesta de creación desconocida, hay riesgo de cargo
sin un ID vinculable: **las rentas reales siguen deshabilitadas** hasta
resolver autenticación del intento, exclusividad global de la cuenta,
identificación inequívoca, vinculación atómica al lease financiero y
apagado confirmado por API. Las pruebas de este PR son simuladas.

## Reserva previa sin contratación (fase segura)

Se añadió `clore_preorder.py` como **libro de exposición local** para preparar
la futura contratación autónoma. No está conectado a Telegram ni al broker
comercial y **no tiene ninguna ruta de API que cree, puje o cancele órdenes**.

Una reserva acepta solamente términos explícitos para **un servidor físico**:
moneda API `USD-Blockchain`, descriptor GPU con variante verificada,
imagen Docker fijada por digest, tarifa diaria, creación, límite total,
duración y cotización con antigüedad máxima de 120 segundos.
Requiere timer Clore activo y heartbeat reciente, una captura autenticada
de inventario completo de `my_orders` con IDs no repetidos, y cálculo de
presupuesto conservador. Persiste atómicamente términos, SHA256 y baseline
de órdenes en SQLite **antes de un eventual create**. Una segunda reserva
o una orden financiera armada bloquean la creación de otra obligación.

La función de conciliación compara nuevas órdenes con el baseline y devuelve
solamente `not_found`, `ambiguous`, `identity_mismatch`,
`price_or_fee_mismatch` o `candidate_unbound`. No enlaza automáticamente
ese candidato a una obligación financiera y no autoriza contratos.
Una reserva caducada sigue bloqueando nuevos planes hasta que el operador
financiero haya conciliado la respuesta desconocida: **el paso del tiempo
no prueba que Clore no creó una orden**. El despliegue por SHA también se
bloquea mientras existan reservas en estado `reserved` o `uncertain`.

**Pendiente imprescindible:** aprobación Telegram ligada criptográficamente
al plan exacto, bloqueo exclusivo de toda creación de órdenes de la cuenta,
un único intento seguro de `create_order`, obtención confiable del nuevo
`order_id` incluso ante timeout, integración con el supervisor de corte,
seguimiento de costes postcancelación y prueba simulada end-to-end.
No se autoriza gastar ni usar este módulo como límite USD garantizado.

Prueba: `python3 -m unittest discover -s extensions/mining-operator -p test_clore_preorder.py -v`

## Contabilidad del saldo USDT/USDC (octubre 2026)

Clore admite pagos de alquiler con USDT y USDC, acreditados en un **saldo
unificado en USD**. En la API, ese saldo y las órdenes cobradas contra él
utilizan el identificador exacto **`USD-Blockchain`**, no `usd`, `usdt` ni
`USDT`. La versión anterior rechazaba erróneamente esas órdenes.

El supervisor ahora acepta exclusivamente `orders[x].currency=USD-Blockchain`
para presupuesto, tarifa diaria, comisión de creación y gasto en unidades de
saldo USD respaldado por stablecoins. Rechaza otras monedas, incluso alias
no documentados, sin hacer conversiones automáticas BTC/CLORE a USD.

Antes de registrar una orden exige respuesta autenticada de `my_orders`
con identidad exacta, Spot, estado activo, marca de tiempo y valores de gastos
verificables. Durante cada tick compara los mismos campos; cualquier moneda,
tarifa o gasto incompatible desencadena intento de cancelación conservadora.
Un POST no confirma el cierre: sólo `expired: true` en la orden.

**No habilita nuevas rentas automáticamente.** Faltan reserva presupuestaria
previa al `create_order`, conciliación de timeouts, límites totales
independientes y medición empírica de PRL y rentabilidad neta para el agente.

Documentación: https://clore.ai/api-docs y
https://docs.clore.ai/getting-started/deposit-withdrawal/supported-currencies

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
