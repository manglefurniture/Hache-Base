# Reservas e idempotencia

Patrón para recursos escasos y efectos repetibles en flujos de pago, reservas, inscripciones, boletos o inventario.

## Reserva de recurso

Una reserva temporal debe almacenar al menos:

- recurso/pedido asociado;
- cantidad o capacidad reservada;
- indicador de reserva activa;
- fecha/hora de expiración;
- estado de negocio.

La reserva se crea dentro de una transacción después de bloquear y verificar disponibilidad. El TTL debe usar la zona/semántica temporal definida por el proyecto; para timestamps técnicos puede usarse UTC si toda la comparación se mantiene coherente.

## Liberación

Debe existir una operación idempotente que:

1. bloquee el recurso/pedido;
2. compruebe si la reserva sigue activa;
3. restituya inventario/cupo exactamente una vez;
4. marque la reserva como liberada;
5. deje evidencia de la causa (expiración, cancelación, fallo al iniciar pago, etc.).

Un job/cron puede barrer reservas expiradas. Ejecutarlo dos veces no debe duplicar stock.

## Claim de efectos secundarios

Para evitar correos, facturas o avisos duplicados ante reintentos:

```sql
UPDATE orders
SET notification_claimed_at = NOW()
WHERE id = :id
  AND paid_at IS NOT NULL
  AND notification_claimed_at IS NULL;
```

Solo quien obtiene una fila afectada ejecuta el efecto. Si el efecto falla, el proyecto puede liberar el claim o persistir `failed_at`/contador para reintentar con una política explícita.

En flujos críticos o de alto volumen, preferir una tabla outbox con clave única por `(event_type, aggregate_id)` y un worker independiente.

## Idempotencia del pago

La tabla de pagos debe imponer unicidad sobre el identificador del proveedor. Un webhook repetido hace UPSERT/lectura del mismo pago; nunca crea dos pagos lógicos por el mismo evento externo.

## Invariantes recomendadas

- stock/cupo nunca negativo;
- una reserva activa se consume o se libera, no ambas dos veces;
- un pago externo único corresponde a un único recurso local;
- estados finales no retroceden por eventos tardíos sin una transición explícita;
- notificaciones repetidas no alteran el estado financiero central.

## Concurrencia

La UI puede prevenir dobles clics, pero la defensa definitiva está en servidor: transacciones, locks, restricciones `UNIQUE`, condiciones atómicas y validación del estado actual.
