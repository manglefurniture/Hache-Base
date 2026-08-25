# Estados temporales e integridad entre vistas

## Objetivo

Evitar inconsistencias cuando una entidad cambia de estado por el paso del tiempo o cuando varias pantallas representan la misma obligación/regla de negocio.

Este patrón aplica a cursos, campañas, promociones, membresías temporales, reservas, eventos, periodos de servicio, ventanas de acceso y cualquier entidad con fecha de inicio y fin.

## 1. El estado temporal se deriva de fechas

Cuando el estado depende únicamente del tiempo, la regla canónica debe poder calcularse desde `fecha_inicio`, `fecha_fin` y la fecha operativa del negocio.

Modelo genérico:

```text
hoy < inicio           -> FUTURE
inicio <= hoy <= fin   -> ACTIVE
hoy > fin              -> ENDED
```

Los nombres visibles del proyecto pueden ser distintos (`PROGRAMADO`, `EN_CURSO`, `TERMINADO`, por ejemplo), pero deben mapear a una sola regla de dominio.

Hache-Base incluye `src/common/DateRangeState.php` para esta clasificación.

## 2. Un estado persistido es una proyección, no una verdad infalible

Puede ser útil guardar un campo `estado` por compatibilidad, consultas o rendimiento. Si ese valor depende del reloj, debe considerarse una proyección sincronizable.

Reglas:

- las lecturas críticas deben poder recalcular el estado desde sus datos fuente;
- cualquier reconciliación persistida debe ser idempotente;
- la reconciliación debe limitarse al contexto autorizado (organización/sede/recurso);
- no depender de una acción manual para cambiar un estado que es puramente temporal;
- no crear triggers o cron jobs si una derivación simple y una reconciliación controlada resuelven el caso.

## 3. Zona horaria operativa explícita

Nunca calcular `hoy`, vencimientos o cambios de estado suponiendo que la zona horaria del VPS coincide con la del negocio.

Cada proyecto debe definir `APP_TIMEZONE` con un identificador IANA válido, por ejemplo:

```env
APP_TIMEZONE=America/Cancun
```

Si el negocio opera en varias zonas horarias, la zona debe pertenecer al contexto correspondiente y viajar explícitamente con la regla.

## 4. Consistencia entre vistas

Dos pantallas, endpoints o reportes que representan la misma obligación no deben decidir su estado con criterios distintos.

Ejemplo genérico de obligación financiera:

```text
actor + recurso exacto + tipo de obligación + estado válido
```

No basta con comprobar que un cliente tiene "algún pago". La consulta debe relacionar el pago con la obligación exacta que la interfaz está mostrando.

La misma definición canónica debe alimentar:

- listados;
- fichas o timelines;
- detalle del recurso;
- formularios de acción;
- reportes relevantes.

## 5. Defensa por capas

La interfaz debe evitar ofrecer una acción que el sistema ya sabe que es inválida, pero la UI nunca sustituye la validación del servidor.

Patrón recomendado:

```text
estado canónico -> UX preventiva -> validación de servidor -> protección transaccional/integridad
```

Ejemplos:

- una obligación pagada muestra `Pagado` y no ofrece un segundo botón de cobro;
- aun si una petición se fuerza manualmente, el servicio rechaza el duplicado;
- una acción sobre un recurso vencido se bloquea en servidor aunque la pantalla esté desactualizada.

## 6. Roles de solo lectura

Una operación de consulta realizada por un rol read-only debe permanecer read-only también en sus efectos secundarios.

Un rol de consulta puede recibir un estado derivado correctamente sin ejecutar reconciliaciones persistentes, housekeeping o escrituras automáticas.

Si una reconciliación debe escribirse, debe ejecutarla un actor o proceso con permiso explícito de mutación.

## 7. Pruebas mínimas obligatorias

Toda regla temporal debe comprobar como mínimo:

1. día anterior al inicio;
2. día exacto del inicio;
3. día exacto del final;
4. día posterior al final;
5. comportamiento en la zona horaria operativa.

Toda obligación que bloquee duplicados debe comprobar:

1. primera operación válida;
2. duplicado rechazado;
3. relación con el recurso exacto;
4. comportamiento tras invalidación/cancelación si el dominio lo permite;
5. consistencia entre las vistas que representan ese estado.

## 8. Qué debe adaptarse en cada proyecto

Hache-Base aporta el patrón y la utilidad temporal. Cada proyecto define:

- nombres de estados visibles;
- entidad/rango de fechas;
- zona horaria;
- criterio exacto de obligación o recurso;
- mecanismo de reconciliación persistida si realmente lo necesita;
- permisos para ejecutar esa reconciliación;
- pruebas específicas del negocio.

No existe una migración universal asociada a este patrón.
