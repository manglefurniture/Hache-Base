# Hache Mining Agent — fase 1: memoria y asesor de oportunidades PRL

**Estado:** módulo propuesto para revisión y ejecución manual/read-only. **No está desplegado**, no se programa un ciclo 24/7, no existe bot de Telegram ni facultad de renta.

## Objetivo

Separar las recomendaciones económicas del mecanismo de gasto. Este asesor evalúa ofertas para verificar utilizando observaciones reales de PRL, y nunca ejecuta una orden de contratación. Una futura IA podrá explicar y diagnosticar, sin saltarse los controles financieros del broker ni los watchdogs independientes.

## Alcance seguro

- Entrada: consultas sanitizadas *vast.search* y *clore.marketplace*. El módulo no necesita credenciales, comandos SSH, acceso a root ni llamadas a red.
- Vast: las cotizaciones pueden omitir almacenamiento, tráfico y facturación después de detener el cómputo. La identificación laptop/desktop debe ser verificada fuera del asesor; el broker todavía no proporciona esa distinción.
- Clore: la consulta read-only no verifica la cantidad exacta de GPU o una puja Spot. Por ello sus resultados solo son candidatos para **verificación de hardware**, nunca para contratar.
- Historial: PRL efectivamente producido, shares aceptadas, horas de cómputo cobradas, GPU, proveedor y minutos hasta el arranque. No inferir PRL desde TH/s. El mero registro de un evidence_id no autentica esa fuente; la integración futura de Kryptex debe validarla.
- Como mínimo 3 observaciones recientes de la misma GPU y proveedor, con shares aceptadas; duración total observada de al menos 3 horas. Historial con validez de 14 días.
- Proyección conservadora: cuartil inferior de PRL por GPU/h; reduce producción por tiempo de arranque, descuenta comisiones y agrega reserva de costos indicada explícitamente.
- Precio de venta PRL facilitado con fecha UTC de observación no superior a 60 minutos. No inventar precios, comisiones, costos o presupuestos.
- Resultado *candidate_for_manual_quote* significa solamente que merece revisión; requiere cotización con todos los cargos, validación de host y autorización única para esa oferta. Vast.rent y Clore.create_order siguen bloqueados.
- Persistencia SQLite privada (directorio 0700, archivo 0600, usuario de servicio dedicado). No subir capturas de minería con datos personales a GitHub.

## Pruebas sin gastos

Guardar la salida JSON completa, ya sanitizada, del broker en offers.json. Para Vast usar *vast.search* con GPU y límites explícitos; para Clore, *clore.marketplace*. No guardar tokens. En la copia read-only de Vast completar campo variant con desktop o laptop **solo después de verificarlo**. No alterar la identidad de la oferta que el broker comprueba.

Preparar measurements.json como lista con campos: evidence_id, provider, gpu_name, variant, observed_at ISO 8601 con zona, gpu_count, billed_hours, prl_mined, setup_minutes, accepted_shares.

Preparar market.json con price_usd_per_prl, price_observed_at, pool_fee_fraction, exchange_fee_fraction, duration_hours, cost_buffer_fraction, extra_charges_usd y min_net_usd. Un gasto adicional cero no garantiza ausencia de cargos.

Comandos:

~~~sh
python3 extensions/mining-operator/mining_advisor.py --database /ruta-privada/prl-history.sqlite --import-measurements /ruta-privada/measurements.json
python3 extensions/mining-operator/mining_advisor.py --database /ruta-privada/prl-history.sqlite --offers /ruta-privada/offers.json --market /ruta-privada/market.json
python3 -m unittest discover -s extensions/mining-operator -p 'test_mining_advisor.py' -v
~~~

## Etapas siguientes, cada una con PR y revisión

1. Ingesta validada de Kryptex, recibos e historial de instancias; billeteras Vast/Salad independientes.
2. Telegram privado con autorización caducable de oferta, host, GPU, tarifa máxima y presupuesto total; chat_id allowlisted, nonce, antirreplay, callback autentificado y registro auditable. La aprobación no sustituye el grant root.
3. Cerebro con modelo IA y herramientas allowlisted de lectura. El modelo interpreta resultados y propone reparaciones; no emite rentas ni comandos privilegiados.
4. Integración real de renta bajo los límites del issue #84 y el guard independiente Clore, cerrando también la ventana de create_order antes de armar lease. Probar timeouts, duplicados, reboot, storage residual, fallos de parada y pérdida del VPS.
5. Timer y servicio continuo solo cuando el sistema completo pase CI, revisión, merge, despliegue versionado y smoke. Docker fijado por digest; confirmar shares reales y cortar pérdidas.

Nunca tratar un precio/hora multiplicado por duración como techo bancario que el proveedor garantice.
