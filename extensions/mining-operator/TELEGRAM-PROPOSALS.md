# Hache Mining Agent — Telegram de propuestas (fase aislada, sin rentas)

## Alcance

Canal privado Telegram, con almacenamiento SQLite para reconocer o rechazar ofertas concretas de Vast.ai. La aceptación se guarda como estado acknowledged: **no crea planes ejecutables, root grants, rentas ni gastos**. No modifica broker, Vast, Clore, Salad, Kryptex o mineros.

La confirmación humana por mensajería es una señal de intención, no puede reemplazar el guard financiero independiente, una nueva cotización ni las puertas de seguridad del issue #84.

## Controles

- telegram_proposals.py solo admite los métodos Telegram sendMessage, getUpdates y answerCallbackQuery sobre HTTPS. Bot dedicado; token protegido con systemd LoadCredential y nunca incluido en repositorio, modelo IA, logs ni mensajes.
- Sin webhook ni apertura de puertos. Verifica user_id, chat_id y chat de tipo privado del propietario antes de aceptar callbacks. No ejecuta comandos de texto.
- Nonce aleatorio de un solo uso, caducidad 5 minutos, SHA256 de propuesta canónica, cursor durable de updates para evitar replay y transacciones SQLite para consumo atómico.
- Oferta vinculada a proveedor/offer_id/machine_id/host_id/GPU/cantidad/tarifa/presupuesto/duración/estimación neta y antigüedad de cotización. Solo admite Vast; el contrato de Clore Spot requiere otra integración.
- Las propuestas repetidas mientras la primera esté activa se rechazan. Un callback expirado, adulterado o desde otro usuario/chat no autoriza nada.
- El asesor y broker deben validar por separado origen de observaciones de Kryptex, rentabilidad neta, cargos residuales, límites y proveedor. El precio mostrado no equivale a un hard cap de facturación.

## Pruebas sin gastos

python3 -m unittest discover -s extensions/mining-operator -p 'test_telegram_proposals.py' -v

Cubren destinatario incorrecto, grupos, replay, expiración, duplicados, precio inválido, mensajes fallidos, modificación de payload y comandos libres ignorados. Ninguna prueba conecta a Telegram o alquila máquinas.

## Plan seguro de despliegue

1. Crear un bot **dedicado** con BotFather. Obtener por un flujo de onboarding seguro el chat_id y user_id privados exactos del propietario. Nunca pedir que pegue token en ChatGPT.
2. Guardar el token en archivo root-only en VPS para LoadCredential. Crear cuenta de servicio aislada sin sudo ni claves de minería. Directorio SQLite privado 0700 y archivo 0600, UMask 0077.
3. Instalar únicamente la versión validada y fusionada de GitHub, mediante la puerta de despliegue existente. No editar código versionado directamente en VPS.
4. Preparar ofertas JSON read-only validadas con campos exactos: provider, offer_id, machine_id, host_id, gpu_name, gpu_count, max_hourly_usd, max_total_usd, max_minutes, projected_net_usd y quote_observed_at. Cotización no mayor de 120 segundos.
5. Comando de registro (no renta):

    python3 telegram_proposals.py --database /var/lib/hache-mining-agent/proposals.sqlite --prepare-file /ruta-privada/oferta.json

6. Encender Telegram con credencial systemd y verificar que los botones funcionan solo para el propietario, con resultado rental_permitted=false. No habilitar rentas.
7. Vincular en fases posteriores datos frescos del asesor y de Kryptex, el bridge de grants root, watchdog financiero y supervisor externo ante pérdida del VPS.

Nunca ejecutar un alquiler solo por recibir acknowledged desde Telegram.


## Menú de acciones de solo lectura (incremento posterior)

El bot existente acepta en el chat privado autenticado \`/start\`, \`/menu\`,
\`/ofertas\`, \`/estado\`, \`/ayuda\`. Los mensajes del radar horario incluyen
un teclado inline con **Vast.ai, Clore.ai, estado, rentabilidad, watchdogs y ayuda**.
El mismo proceso receptor de Telegram atiende los callbacks; **no montar otro
\`getUpdates\` sobre el token existente**.

Solo utiliza \`/var/lib/hache-mining-market/report.json\`, compartido por
el scout mediante grupo \`hache-telegram\`, con validación de propietario,
permisos, sin symlinks, antigüedad máxima de 90 minutos, origen dual e
indicadores \`rental_permitted=false\` y \`net_profit_verified=false\`.
Una lectura ausente o antigua se indica como **no disponible**. Se escapan
los nombres proporcionados por hosts antes de enviar HTML a Telegram.
El botón no provoca un escaneo nuevo: presenta el último escaneo horario.

**Límites explícitos:** los botones no rentan, pujan, cancelan, reinician ni
cambian presupuestos. El estado del watchdog operativo tampoco se afirma
sin un canal de telemetría auténtico. Para habilitar acciones comerciales
se necesitan grants por oferta y guardias financieros independientes de
Vast y Clore, de acuerdo con issues #84 y #109.

Prueba sin red ni gasto:
\`python3 -m unittest discover -s extensions/mining-operator -p test_telegram_menu.py -v\`

Despliegue: usar exclusivamente el SHA revisado y fusionado con
\`deploy/deploy-gpu-variants.sh\`, que ahora incluye estas regresiones,
y conservar credenciales, usuario \`hache-telegram\` y watchdogs existentes.
No modificar scripts activos manualmente en VPS.

## Búsqueda Spot a petición del propietario (solo lectura)

Desde el chat privado, /gpu 5090, /gpu 5090 laptop o
/gpu 4070 ti super escritorio x2 ejecuta un GET nuevo al marketplace
público de Clore. No se usan API keys, no se conecta al broker comercial
ni se conceden permisos adicionales. Los comandos de grupos/otros usuarios
son ignorados. El filtro busca un servidor completo con el número de GPU
solicitado, sin suponer alquiler parcial. Muestra coincidencias hasta 100
y permite navegar en páginas de cinco. Cualquier truncamiento se declara.

Las cotizaciones presentan únicamente el mínimo Spot publicado en
USD-Blockchain y el precio On-Demand del servidor completo. Son precios
indicativos, nunca una puja ejecutable o ganadora. Las variantes escritorio
y Laptop se infieren de etiquetas del host, no de una comprobación
del hardware. La ordenación es por piso Spot más bajo; NO proclama
rentabilidad neta. Faltan un historial verificable de PRL por GPU,
precio neto realizable, cargos finales y dificultad actual.

Seleccionar #ID registra solo la identidad del anuncio mostrado,
vinculada al ID de mensaje Telegram y a un snapshot que expira
en 180 segundos. El botón no genera una propuesta financiera ni orden
de compra/puja. Selecciones repetidas o de mensajes ajenos son rechazadas.
Ningún input de Telegram puede saltarse el consentimiento exacto
de una orden, presupuesto y watchdog financiero.

Futura fase comercial (NO activada): reconsultar una oferta elegida
antes de pujar, comprobar cambios de precio/servidor, aprobación explícita
de tasa Spot máxima, presupuesto total y deadline, obligación financiera
duradera antes de create_order, reconciliación ante timeout y asociación
de minero/wallet/worker con una orden concreta.
Hasta cerrar estas garantías rental_permitted=false.

El componente telegram_clore_search.py hace solo GET contra
https://api.clore.ai/v1/marketplace, impone un límite de respuesta y no
acepta URLs suministradas por el usuario. Pruebas sin gasto:
python3 -m unittest discover -s extensions/mining-operator -p test_telegram_clore_search.py -v

## Consulta segura de competencia Spot antes de pujar (fase 2, sin gasto)

Una vez elegida una oferta del comando /gpu, el bot muestra el botón
Consultar competencia Spot. Ese botón está ligado al mensaje privado
enviado realmente al propietario y al server_id del snapshot (180 s).
Cualquier otro usuario/chat, ID falseado o resultado caducado se rechaza.

Arquitectura:
- Telegram (usuario hache-telegram) solo conoce el ID del servidor. Se
  conecta al socket Unix fijo /run/hache-clore-spot/quote.sock, grupo
  hache-telegram y permisos 0660. No puede leer la API key ni ejecutar shell.
- Servicio especializado (usuario hache-miner) comprueba SO_PEERCRED y
  consulta SOLO GET https://api.clore.ai/v1/spot_marketplace?market=ID,
  con la clave privada LoadCredential=clore_key del propio systemd.
- El servidor valida los tipos y devuelve únicamente: ID, hora UTC, piso
  USD-Blockchain, puja más alta convertida a USD entre TODAS las monedas,
  recuentos, MRL, ilustración +1 % y advertencias de no ejecución.
- El cliente vuelve a verificar procedencia, caducidad <=120 s y banderas
  rental_permitted=false, executable_quote=false, net_profit_verified=false.
- Respuestas inválidas, sin USD, mercado privado, host desconectado,
  datos truncados, tipo monetario ambiguo o fallos de API se rechazan.

La oferta orientativa +1 % es una estimación NO ejecutable: Clore puede
aplicar mínimos, topes, otros incrementos, fees y competencia cambiante.
Un piso Spot anunciado no asegura que una puja gane. Tampoco equivale
al neto de minería PRL. No hay POST, create_order ni set_spot_price.

Instalación root separada (solo tras desplegar un release exacto revisado):
  bash /opt/hache-mining-operator/current/deploy/install-clore-spot-quote.sh

Se crean las unidades hache-mining-operator-clore-spot-quote.socket y
.service. El token sigue privado en /etc/hache-miner/clore-api-key (systemd
LoadCredential), nunca pasa a Telegram. El servicio de quote no
proporciona contratos de gasto, cancelaciones ni pujas. No cambiar el
canal de Telegram a hache-miner ni incluir la key en un archivo grupal.

Para seguir hacia la contratación real: análisis PRL con producción
observada y cargos completos, límite de puja y presupuesto total,
aprobación de un solo uso, pre-order financiero duradero, create_order
idempotente o reconciliable, provisionamiento y worker/ID vinculados,
alarma de shares y cierre verificado de la renta. Mantener bloqueado.

## Escenario PRL después de seleccionar una GPU (fase 3, SIN gasto)

El mensaje de selección de /gpu incluye el botón "Escenario de rentabilidad PRL",
vinculado al mensaje y servidor seleccionados, con caducidad de 180 segundos.
El propietario puede consultarlo sin dar credenciales ni acceder al broker.

La consulta hace un GET fijo a https://www.pearlsonar.com/pools, lee solo
contenido visible del HTML y exige encontrar una tarjeta Kryptex con
"Net yield" (PRL/PH/s/día) y la referencia OTC de PRL. Se rechazan
respuestas ausentes, imprecisas o fuera de rango. La publicación no
garantiza un precio de ejecución de venta ni mide una GPU específica.

Calibraciones históricas explícitas, NO verificadas para una instancia
que aún no se ha alquilado: RTX 5090 Laptop 330 TH/s, RTX 5090
escritorio 380 TH/s, RTX 4070 Ti SUPER escritorio 155 TH/s y
RTX 4090 escritorio 300 TH/s. Otros modelos/variantes se rechazan.
No inferir que la etiqueta de Clore demuestra el hardware real.

Escenario base: hashrate histórico por GPU × yield 24 h del pool ×
85% de disponibilidad × precio OTC × 90% de realización de venta.
Costo: piso Spot USD/h del host × 24 × factor 1.05 de reserva.
Se muestra margen base, escenario adverso de dificultad +30% y precio
PRL -20%, y tarifa de equilibrio adverso. Estas reservas son
suposiciones configuradas, no tasas garantizadas. No incluir otros
costos financieros/fiabilidad/creación/competencia de puja como si
estuvieran verificados. La cifra puede ser errónea incluso con
un escenario positivo.

No se crea una oferta, no se cambia el precio Spot de una orden,
no se activa rental_permitted y no se reclama "rentabilidad neta
verificada". No utilizar este escenario como autorización para pujar.
Las pujas competirán por su precio ejecutable, no el piso publicado.

Pruebas:
python3 -m unittest discover -s extensions/mining-operator -p test_telegram_prl_scenario.py -v

## Corrección 28/10: fuente del ROI y clave privada Spot

Spot utiliza la ruta root existente del guard financiero:
/etc/hache-miner/secrets/clore_api_key. La clave solo se entrega al
servicio de consulta hache-miner mediante systemd LoadCredential.
No se copia a Telegram ni se introduce en argumentos.

PearlSonar puede agotar tiempo de espera desde el VPS. Para evitar una
pantalla vacía de forma recurrente, la rentabilidad PRL consulta primero
https://pearltrack.io/pools y, si falla, intenta
https://www.pearlsonar.com/pools. El valor USD/PRL de PearlTrack es
IMPLICITO: se divide el beneficio en USD/PH/dia por el yield en
PRL/PH/dia, cifras redondeadas que no constituyen un precio de venta
ni orden ejecutable. Los resultados identifican esa aproximacion.

Ambas conexiones son GET publico HTTPS; si ambas fallan el escenario
se muestra no disponible. Nunca se inventan cifras ni se habilitan
pujas o create_order. Despues de desplegar por commit exacto, activar
el socket de consulta separado desde root y comprobar el estado.

## Comparacion de ofertas PRL del listado Spot

En cada pagina de /gpu, el boton "Comparar escenarios PRL" permite
evaluar las ofertas guardadas de la misma busqueda, con un solo GET
publico a PearlTrack o PearlSonar. El callback requiere el chat
privado autorizado, message_id de la pagina, nonce valido y snapshot
no vencido. No reordena ni altera el marketplace ni las propuestas
financieras.

El ranking usa margen ADVERO antes del margen base, por identificador
del servidor. Solo se calculan GPUs con rendimiento historico
calibrado; otras quedan como "sin referencia". Cada fila muestra
coste al PISO Spot publicado, margen base, margen adverso y la
etiqueta "descartar" cuando el margen calculado no es positivo.
Una estimacion positiva NO verifica la rentabilidad ni equivale
a una puja ganadora: faltan hashrate real, coste adjudicado y
precio de venta ejecutable. Nunca auto-contratar por este ranking.

Salida limitada a ocho filas y snapshot maximo de 100 anuncios, con
indicacion de cuantas ofertas quedan fuera de la tabla. Si no hay
fuente publica valida o el snapshot vence, falla cerrado sin cifras.
Sin permisos de gasto, credenciales Clore, create_order o bids.

## Solicitud de limites de puja Clore desde Telegram, SIN COMPRAS (fase 4)

Tras `/gpu 5090 laptop` y Seleccionar #ID, el propietario puede enviar:
`/puja ID PRECIO_MAXIMO_USD_DIA PRESUPUESTO_USDT MINUTOS`.
Ejemplo ficticio de formato: `/puja 119661 5.70 10.00 60`.
El ID de servidor debe estar seleccionado en el snapshot privado y
vigente; la cuenta Telegram NO recibe clave financiera ni capacidad POST.

El bot pide una cotizacion autenticada reciente al servicio exclusivo
de lectura Clore, compara la puja propuesta con piso y competencia,
confirma la duracion `mrl` y exige presupuesto suficiente para la
exposicion hipotetica del periodo * 1.20 + US$1 de holgura de
comision ilustrativa (NO es una tarifa verificada). Tambien
recalcula el margen PRL adverso para el PRECIO propuesto, no solo
el piso del host. No se ofrece confirmar limites si ese margen
es cero o negativo, faltan datos o el snapshot ha caducado.
La validacion es conservadora, no una promesa de rentabilidad.

El resultado es una propuesta efimera en SQLite de hache-telegram,
asociada al `update_id`, `message_id` exacto, hash inmutable de
terminos, id de servidor, limite diario, limite de gasto y minutos.
Caduca en <= 90 segundos. Los botones
"Confirmar limites (SIN PUJAR)" y "Cancelar" solo cambian la
decision local una vez, rechazan replay de otro chat/mensaje,
hash manipulado y expiracion.

**No es una autorización financiera**: `rental_permitted=false`,
`financial_grant=false`, `provider_mutation=false`.
La confirmacion no firma una atestacion reutilizable por el agente de
alquiler, NO registra ninguna orden, NO envia `create_order` ni
`set_spot_price`. La politica de ejecucion sigue cerrada.

Para habilitar renta comercial faltan: imagen de minero fijada
por digest y comprobada en Clore; comprobacion GPU real; consulta
de comisiones de creacion/moneda y presupuesto ejecutable; asociar
la solicitud con `clore_preorder`, consentimiento Ed25519 verificado
por `hache-miner`, write-ahead antes del POST, reconciliacion de
timeouts y `order_id`, orden con identidad segura y monitor
de shares + cancelacion verificable, prueba de fallo sin gasto y
autorizacion expresa de una renta de prueba con presupuesto cerrado.
Solo ese futuro ejecutor independiente puede solicitar gastos.
La ausencia de mas pujas no implica beneficio ni disponibilidad.

Prueba: `python3 -m unittest discover -s extensions/mining-operator -p test_telegram_clore_budget.py -v`.
