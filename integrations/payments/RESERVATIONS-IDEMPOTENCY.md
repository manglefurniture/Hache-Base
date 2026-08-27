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

Solo quien obtiene una fila afectada ejecuta el efecto. El claim evita que dos workers disparen el mismo efecto al mismo tiempo, pero **no basta por sí solo para garantizar idempotencia frente a fallos ambiguos de red**.

Antes de llamar a un proveedor externo, el proyecto debe generar y persistir una clave de idempotencia estable para ese efecto, por ejemplo a partir de `(event_type, aggregate_id)` o del identificador único de una fila outbox. Si el proveedor soporta idempotency keys, la misma clave debe reutilizarse en todos los reintentos de la misma operación lógica.

Si una llamada externa termina con timeout, desconexión o respuesta indeterminada, no se debe liberar el claim y repetir con una operación nueva de forma ciega: el proveedor pudo haber aceptado el correo, factura o aviso antes de perderse la respuesta. En ese caso se debe:

1. conservar el mismo identificador/idempotency key;
2. consultar o reconciliar el estado con el proveedor cuando exista una API para ello;
3. reintentar únicamente con la misma clave idempotente, o marcar el efecto para revisión si el proveedor no ofrece una forma segura de determinar el resultado.

El claim puede liberarse sin riesgo cuando el fallo ocurrió de forma inequívoca **antes** de intentar el efecto externo, o cuando el proveedor confirma que la operación no fue aceptada. No se recomienda liberar el claim automáticamente después de un fallo ambiguo.

Para flujos críticos o de alto volumen, preferir una tabla outbox con clave única por `(event_type, aggregate_id)`, identificador estable del efecto, estado de entrega y un worker independiente. La outbox debe conservar el mismo identificador lógico durante todos los reintentos.

## Idempotencia del pago

La tabla de pagos debe imponer unicidad sobre el identificador del proveedor. Un webhook repetido hace UPSERT/lectura del mismo pago; nunca crea dos pagos lógicos por el mismo evento externo.

## Invariantes recomendadas

- stock/cupo nunca negativo;
- una reserva activa se consume o se libera, no ambas dos veces;
- un pago externo único corresponde a un único recurso local;
- estados finales no retroceden por eventos tardíos sin una transición explícita;
- un efecto externo conserva la misma clave idempotente durante todos sus reintentos;
- notificaciones repetidas no alteran el estado financiero central.

## Concurrencia

La UI puede prevenir dobles clics, pero la defensa definitiva está en servidor: transacciones, locks, restricciones `UNIQUE`, condiciones atómicas y validación del estado actual.
