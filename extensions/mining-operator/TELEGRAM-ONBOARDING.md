# Telegram onboarding — Hache Mining Agent (fase sin gastos)

El bot registra propuestas de ofertas, aceptaciones y rechazos, pero **no renta GPUs, ejecuta comandos, instala mineros ni autoriza gastos**. Las aprobaciones no sustituyen controles root.

## Requisitos

- Bot de Telegram creado con BotFather y token root-only en /etc/hache-mining-agent/telegram_token, modo 0600 y directorio 0700.
- Abrir el bot en un chat privado, pulsar Start y después enviar el código temporal de vinculación (/pair CODIGO) que se genera localmente en ConnectBot.
- Root disponible temporalmente mediante ConnectBot. gpt-agent continúa sin sudo general ni lectura de secretos.
- Código de GitHub ya revisado, integrado con checks verdes y SHA concreto de 40 caracteres. Nunca descargar una rama mutable sin comprobar SHA.

## Bootstrap root desde ConnectBot

Usar el SHA exacto del release integrado, reemplazando REVIEWED_SHA después de verificar GitHub:

~~~sh
set -Eeuo pipefail
SHA=REVIEWED_SHA
[[ "$SHA" =~ ^[0-9a-f]{40}$ ]]
DEST="/opt/hache-mining-agent/releases/$SHA"
git clone --depth 1 --branch main https://github.com/manglefurniture/Hache-Base.git "$DEST"
test "$(git -C "$DEST" rev-parse HEAD)" = "$SHA"
python3 -m unittest discover -s "$DEST/extensions/mining-operator" -p 'test_telegram_*.py'
bash -n "$DEST/extensions/mining-operator/deploy/install-telegram-proposals.sh"
ln -s "$DEST/extensions/mining-operator" /opt/hache-mining-agent/.current-onboarding
mv -Tf /opt/hache-mining-agent/.current-onboarding /opt/hache-mining-agent/current
# En ConnectBot generar un código aleatorio; enviarlo EN PRIVADO al bot como /pair CODIGO
PAIR="$(python3 -c 'import secrets; print(secrets.token_hex(8))')"
printf 'Envia /pair %s al bot y pulsa Enter en ConnectBot: ' "$PAIR"
read -r _
bash "$DEST/extensions/mining-operator/deploy/install-telegram-proposals.sh" "$SHA" "$PAIR"
unset PAIR
~~~

Si el destino ya existe, no sobrescribir: validar contenido y SHA o abortar. No ejecutar comandos con SHA de ejemplo.

El instalador exige token protegido, descubre exactamente un chat privado con /pair CODIGO reciente (dentro de 5 minutos) mediante HTTPS de Telegram, guarda user_id/chat_id en archivo root-only, crea usuario hache-telegram aislado, instala desde el release la unidad systemd y la inicia. Token solo por LoadCredential y datos en directorio propio hache-mining-telegram (0700). Envia un mensaje de prueba fijo.

Debe mostrar TELEGRAM_TEST_MESSAGE_SENT=true y TELEGRAM_SERVICE=active. Si hay varios chats que han enviado el código temporal, ninguno o mensajes vencidos, aborta, sin escoger un destinatario arbitrariamente. La credencial nunca debe ser pegada en ChatGPT.

## Diagnóstico

~~~sh
systemctl is-active hache-mining-agent-telegram.service
systemctl show hache-mining-agent-telegram.service -p Result -p NRestarts
systemctl is-active hache-mining-operator.socket
~~~

Un fallo de Telegram no debe modificar la minería productiva ni el watchdog. Detener solamente el servicio nuevo para revertir.

## Pendiente

Unir ofertas realmente validadas por Kryptex con propuestas automáticas, medir rentabilidad neta y conectar autorización comercial solo después de cerrar issue 84. No declarar al agente listo para rentar de forma autónoma.
