# Clore: intercambio firmado de consentimiento (sin gasto)

Este incremento conecta dos identidades separadas únicamente en el plano de auditoría:

- hache-telegram: firma una decisión privada ya registrada como acknowledged, desde su SQLite y una futura clave Ed25519 privada de 32 bytes.
- hache-miner: recibe el JSON firmado por un pipe local, verifica la firma contra una clave pública anclada por el administrador y registra verified_only en la SQLite financiera que ya contiene una reserva exacta y un heartbeat reciente.

No crea un grant financiero, no habilita rental_permitted, no llama a Clore para crear ni cancelar órdenes y no modifica las unidades de producción. Una firma de Telegram no autoriza por sí sola un POST.

## Condiciones para futura activación administrada

1. Autorizar de manera independiente la creación y custodia de una identidad Ed25519 de Telegram. Este PR no instala llaves en producción.
2. Crear las rutas de claves privadas/públicas con propietario, permisos y auditoría adecuados sin compartir bases de datos ni claves privadas.
3. Confirmar que el watchdog Clore independiente tiene timer activo y heartbeat reciente; crear previamente una reserva Clore exacta en la cuenta financiera con inventario autenticado completo.
4. Mientras nonce, cotización, reserva y firma sigan vigentes, ejecutar ambas partes mediante pipe administrado, sin escribir el recibo ni la clave en logs. Solo el UID efectivo hache-telegram puede exportar; solo hache-miner puede importar. La clave pública debe pertenecer a root.

Ejemplo conceptual, NO ejecutar sin instalación/autorización administrativa:

    set -o pipefail
    runuser -u hache-telegram -- python3 /opt/hache-mining-agent/current/clore_consent_exchange.py export \
      --db /var/lib/hache-mining-telegram/proposals.sqlite \
      --nonce "NONCE_APROBADO" --private-key "CLAVE_PRIVADA_PROTEGIDA" |
    runuser -u hache-miner -- python3 /opt/hache-mining-operator/current/clore_consent_exchange.py import \
      --db /var/lib/hache-mining-operator/clore-cancel.sqlite3 \
      --reservation-id "RESERVA_EXACTA" --public-key "CLAVE_PUBLICA_ROOT"

El importador rechaza recibos malformados o excesivos, firmas y términos alterados, expiración, repetición, watchdog sin timer, base de datos ajena, archivo de clave permisivo y reserva inexistente. No comparte tokens del bot ni API keys de Clore.

## Bloqueos pendientes para alquiler real

- Grant financiero de un solo uso asociado al consentimiento + reserva + oferta y presupuesto.
- Exclusividad de cuenta verificable, evidencia inequívoca de order_id y vinculación atómica con watchdog; corte financiero independiente.
- Ejecutor de un solo POST con reconciliación ante timeout.
- Aprovisionamiento Docker por digest, shares verificadas, ingresos PRL, costos y rentabilidad neta.
- Simulación completa de fallos y autorización financiera expresa de una oferta concreta.

Regresión sin gasto: python3 -m unittest discover -s extensions/mining-operator -p test_clore_consent_exchange.py -q

Este documento no es una instrucción para activar alquileres.
