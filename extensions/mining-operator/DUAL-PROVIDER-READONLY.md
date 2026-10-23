# Hache Mining Agent — dos APIs de GPU: Vast.ai y Clore.ai

**Estado:** fase de observación/read-only. No autoriza rentas, pujas, órdenes,
aumento de límites, instalación de mineros ni gasto.

## Vast.ai

Leer exclusivamente el broker local y operaciones read-only `vast.search`.
Son ofertas On-Demand, con precio que puede depender de almacenamiento (la
búsqueda original cotiza 5 GiB). Verificar nombre, cantidad y variante real de
GPU desktop/laptop; tampoco estimar PRL desde TH/s. Sin historial reciente,
precio PRL fresco o confiabilidad suficiente, nunca marcar rentable.

## Clore.ai

El mismo broker ya consulta `GET /v1/marketplace` por HTTPS, desde la API de
Clore, sin entregar su token privado a `gpt-agent`. El parser ahora devuelve:

- `prl_gpu`: los 10 anuncios On-Demand más baratos, **por servidor entero**.
- `prl_gpu_spot_floor`: los 10 anuncios con el **mínimo Spot** en USD/h más bajo.
- `prl_gpu_5090`: anuncios con RTX 5090 para revisión específica.
- `gpu_count_verified`: cantidad solo si el prefijo exacto de `specs.gpu`
  concuerda con longitud de `gpu_array` (si no, `null`).
- `gpu_variant_verified=false`: jamás inferir desktop por ausencia de "Laptop".
- `spot_floor_usd_hour`: precio **mínimo** por hora, no una orden cotizable
  ni la puja ganadora; el USD se acepta solo si lo publica Clore como
  USD-Blockchain o equivalencia USD oficial. Nunca convertir bitcoin/Clore a
  USD sin cotización externa fiable.

`GET /v1/spot_marketplace?market=ID` permite consultar la competencia real
de Spot, pero requiere token protegido y aún **no** está incorporado al broker
read-only. No interpretar el piso como oferta de renta ejecutable. Una puja Spot
puede perder la prioridad y detener la GPU inesperadamente.

Aun con precio mínimo conocido, requieren validación: identidad del host,
cantidad y variante de GPU, disponibilidad actual, tarifa ganadora,
comisión de creación, overclock, tarifas adicionales, cargo posterior a
cancelación y límites del watchdog (issue #84 y guard de Clore).

## Comparación deterministicamente segura

El asesor `mining_advisor.py` admite dos ficheros JSON sanitizados obtenidos
del broker, y el archivo de precio de venta PRL con marca UTC y comisiones
explícitas:

~~~sh
python3 extensions/mining-operator/mining_advisor.py \
  --database /ruta/privada/observaciones.sqlite \
  --offers-vast /ruta/privada/vast.json \
  --offers-clore /ruta/privada/clore.json \
  --market /ruta/privada/prl-mercado.json
~~~

La salida conserva proveedor por oferta y `renting_enabled=false`. Una
cotización de Clore lleva `needs_verification` y motivos detallados;
no incluye beneficio neto hasta cerrar todas las verificaciones anteriores,
aunque existan antiguas muestras de PRL. Los precios Clore se ocultan cuando
el snapshot falta, es futuro, o supera 5 minutos. Si falta una de las dos
consultas, la comparación doble falla; nunca sustituye una API caída con
información fabricada.

Los datos del pool Kryptex pertenecen a la billetera. No se acreditan PRL
a una GPU ni a un proveedor sin identificador y ventana de medición que lo
justifiquen, aunque la base del VPS tenga observaciones. Comparar primero
precio informativo; comprobar producción real por GPU para estimar neto
posteriormente. Clore y Vast conservan sus propias muestras.

## Pruebas

~~~sh
php extensions/mining-operator/test_clore_market.php
python3 -m unittest discover -s extensions/mining-operator -p 'test_mining_advisor.py'
~~~

No hace falta copiar los tokens de los proveedores al bot de Telegram.
El bot ya existente es un canal privado sin permiso de alquilar. Aún falta
automatizar alimentación continua de informes auditados desde ambos brokers
al bot, y mantener el watchdog financiero y autorizaciones independientes
antes de probar una compra de GPU.
