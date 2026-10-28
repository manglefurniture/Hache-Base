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
