# Hache Mining Agent — comparador automático Vast + Clore (solo lectura)

## Alcance y seguridad

Cada hora (UTC, con desplazamiento aleatorio de hasta 4 min) se solicita al
**broker local preexistente** una consulta read-only `vast.marketplace` y otra
`clore.marketplace`. El broker mantiene las credenciales de los proveedores;
el proceso lector `gpt-agent` no puede leerlas.

- Vast: ofertas On-Demand verificadas, con fiabilidad anunciada >=90 %,
  precio USD/h del equipo completo y diversidad por modelo/variante/núm. de GPU.
  El nuevo broker consulta hasta 160 anuncios para devolver **hasta 80**
  representantes. Es una **muestra parcial** del mercado, no todos los hosts.
- Clore: hasta 80 representantes, incluyendo Laptop y modelos con
  variante no verificada. El Spot es **precio mínimo ofertado**, nunca la
  puja ganadora ni la tarifa final; no se crea ninguna puja.
- El lector `mining_market_scout.py` consulta únicamente dos nombres fijos del
  broker por Unix socket; las credenciales nunca salen del broker. No acepta
  órdenes comerciales ni comandos arbitrarios de usuario.
- La observación reciente de Kryptex se obtiene únicamente como marca temporal
  agregada de `hache_miner.pool_observations`, **sin leer ni publicar
  direcciones o saldos de billeteras**. Los saldos del pool no miden PRL por GPU.
- El informe sanitizado se guarda en
  `/var/lib/hache-mining-market/report.json`, propietario `gpt-agent`,
  grupo `hache-telegram`, directorio 0750, archivo 0640.
- El notificador `hache-telegram` no recibe permisos para el socket del
  broker ni claves de Vast, Clore o DB. Solo puede leer el informe, recibe el
  token de Telegram a través de `LoadCredential` de systemd y envía mensajes
  al chat privado ya emparejado.
- Se verifica frescura del informe, permisos, propietario, integridad estructural
  de los datos y ausencia de afirmaciones sobre ganancias o alquiler autorizado.
  Si falla cualquiera de las dos APIs, **no hay mensaje ni comparación
  falseada**; el timer volverá a intentarlo en la siguiente hora.
- Se envía un primer resumen, después como máximo 2 mensajes por día
  (zona Cancún), mínimo 6h entre alertas, un resumen a las 24h y alertas
  intermedias solo ante mejoras >=12% en la **misma familia/variante/cantidad**
  del costo On-Demand. Un piso Spot menor por sí solo nunca genera alerta.
- `vast.rent` permanece deshabilitado. No se emiten `prepare`, `execute`,
  `vast.start`, pujas, contrataciones ni órdenes de parada.
- Sin PRL real por GPU y sin precio de venta verificable con comisiones y
  tarifas totales, **ninguna oferta se considera rentable**. Los mensajes
  muestran tarifas indicativas para revisión, no sugerencias financieras
  definitivas.

## Activación (solo como root, después de CI y merge)

Primero desplegar **el mismo commit exacto** a los dos servicios
`hache-mining-operator` y `hache-mining-agent-telegram` usando
`deploy/deploy-gpu-variants.sh` (el procedimiento seguro, con rollback,
ya usado en el PR #115). Luego:

~~~bash
bash /opt/hache-mining-operator/current/deploy/install-market-scout.sh SHA_FUSIONADO
~~~

El instalador exige que ambas versiones productivas sean el SHA indicado.
Prueba el broker, las proyecciones Clore/Vast, el nuevo notificador y su
deduplicación; instala unidades root-owned y activa el timer horario.
Realiza **un primer escaneo real** sin modificar instancias, seguido de
un mensaje de Telegram. Si la primera consulta o entrega falla, el timer se
deshabilita y las unidades actuales de minería/Telegram permanecen intactas.

Ver estado sin imprimir tokens:

~~~bash
systemctl is-active hache-mining-market-scout.timer
systemctl list-timers --all | grep hache-mining-market-scout
journalctl -u hache-mining-market-scout.service -n 30 --no-pager
journalctl -u hache-mining-market-notifier.service -n 30 --no-pager
~~~

Desactivar únicamente las nuevas notificaciones (sin tocar GPU ni watchdog):

~~~bash
systemctl disable --now hache-mining-market-scout.timer
~~~

## Siguiente etapa para rentabilidad neta

Conseguir evidencias aisladas por modelo, variante, proveedor y alquiler
(SRBMiner shares aceptados y PRL atribuidos verificablemente) más precio
actual de venta real y fees. Solo con datos recientes y costos all-in
pueden publicarse ganancias netas. No inventar una conversión TH/s a PRL.
