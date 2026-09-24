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

## 5. Cambios con vigencia futura

Cuando una relación, plan, membresía, tarifa, permiso o servicio empieza en una fecha futura, no debe sustituir prematuramente el estado vigente.

Patrón recomendado:

```text
valor_actual
valor_programado
vigente_desde
```

Antes de `vigente_desde`, el sistema debe conservar el valor actual y representar el cambio como futuro. Al alcanzar la fecha efectiva, la promoción del valor programado debe ser idempotente y respetar el contexto autorizado.

Reglas:

- `FUTURE` o `PROGRAMADO` no equivale a `PENDIENTE`, `MOROSO` ni `SIN DERECHO`;
- una obligación futura pagada por adelantado sigue perteneciendo a su periodo futuro y no debe activar artificialmente el periodo actual;
- la interfaz debe distinguir entre "todavía no inicia" y "debe una obligación vigente";
- un cambio de fecha, ciclo o periodo puede reconciliar registros sin historial, pero no debe reescribir evidencia financiera existente;
- si existe historial incompatible con el cambio solicitado, la operación debe bloquearse o requerir un flujo explícito de reversión/corrección.

Ejemplo genérico:

```text
hoy: 25/08
servicio actual: ninguno
servicio programado: Plan A desde 01/09
obligación de septiembre: PAGADA

resultado correcto hoy:
- estado del servicio: INICIA 01/09
- obligación futura: SEPTIEMBRE PAGADA
- no crear deuda de agosto
- no activar Plan A antes del 01/09
```

## 6. Inmutabilidad del historial financiero

Una obligación con pagos, cobros, folios, conciliaciones o cualquier otro historial financiero ya no debe tratarse como una fila técnica libremente reconciliable.

Antes de mover, sustituir, eliminar o recalcular una obligación por cambios de periodo/ciclo/fecha efectiva, comprobar al menos:

1. que permanece pendiente;
2. que no tiene importe cobrado;
3. que no existen pagos asociados;
4. que no existe otro historial financiero que deba conservarse.

Las obligaciones técnicas todavía vacías pueden reconciliarse de forma controlada. Si existe evidencia financiera, preservar el registro y usar un flujo explícito de corrección, cancelación o reversión según el dominio.

## 7. Defensa por capas

La interfaz debe evitar ofrecer una acción que el sistema ya sabe que es inválida, pero la UI nunca sustituye la validación del servidor.

Patrón recomendado:

```text
estado canónico -> UX preventiva -> validación de servidor -> protección transaccional/integridad
```

Ejemplos:

- una obligación pagada muestra `Pagado` y no ofrece un segundo botón de cobro;
- aun si una petición se fuerza manualmente, el servicio rechaza el duplicado;
- una acción sobre un recurso vencido se bloquea en servidor aunque la pantalla esté desactualizada.

## 8. Roles de solo lectura

Una operación de consulta realizada por un rol read-only debe permanecer read-only también en sus efectos secundarios.

Un rol de consulta puede recibir un estado derivado correctamente sin ejecutar reconciliaciones persistentes, housekeeping o escrituras automáticas.

Si una reconciliación debe escribirse, debe ejecutarla un actor o proceso con permiso explícito de mutación.

## 8.1 Cobertura forward-only e historia no capturada

Una relación temporal, actividad o métrica puede empezar a capturarse después de que ya existían registros del dominio. En ese caso, el proyecto debe conservar un marcador explícito de inicio de cobertura y declarar que la historia previa no fue reconstruida.

Reglas:

- un resultado anterior al marcador queda `out_of_coverage` o `not_evaluated`, no en cero;
- no atribuir una relación, acción o carga histórica desde la configuración actual;
- una corrección posterior se registra como corrección, no como reemplazo silencioso de una lectura/snapshot anterior;
- `history_reconstructed=false` es el default conceptual; una reconstrucción excepcional necesita autoridad, evidencia y decisión explícita del proyecto;
- una lectura viva/reconciliable debe etiquetarse como tal; un snapshot histórico necesita su corte y significado preservados de forma durable.

`DateRangeState` sigue resolviendo rangos de vigencia. La cobertura de evidencia pertenece al read model que consume esos rangos; no se infiere del estado temporal actual. Consultar `templates/READ-MODEL-CONTRACT.md`.

## 9. Pruebas mínimas obligatorias

Toda regla temporal debe comprobar como mínimo:

1. día anterior al inicio;
2. día exacto del inicio;
3. día exacto del final;
4. día posterior al final;
5. comportamiento en la zona horaria operativa.

Todo cambio con vigencia futura debe comprobar además:

1. el valor programado no sustituye al actual antes de tiempo;
2. el día efectivo se promueve correctamente;
3. un pago anticipado pertenece al periodo futuro correcto;
4. "no iniciado" no se representa como deuda vigente;
5. cambiar periodo/ciclo reconcilia únicamente obligaciones sin historial;
6. una obligación con historial financiero bloquea la reescritura destructiva.

Toda obligación que bloquee duplicados debe comprobar:

1. primera operación válida;
2. duplicado rechazado;
3. relación con el recurso exacto;
4. comportamiento tras invalidación/cancelación si el dominio lo permite;
5. consistencia entre las vistas que representan ese estado.

## 10. Qué debe adaptarse en cada proyecto

Hache-Base aporta el patrón y la utilidad temporal. Cada proyecto define:

- nombres de estados visibles;
- entidad/rango de fechas;
- zona horaria;
- criterio exacto de obligación o recurso;
- campos o estructura usados para programar vigencia futura;
- mecanismo de promoción/reconciliación persistida si realmente lo necesita;
- permisos para ejecutar esa reconciliación;
- criterios que convierten una obligación en historial financiero protegido;
- pruebas específicas del negocio.

No existe una migración universal asociada a este patrón.
