# Reglas de negocio

## Objetivo

Evitar que decisiones importantes queden escondidas entre endpoints, SQL, triggers y conocimiento informal.

## Plantilla para una regla

Cada regla relevante debe registrar:

- **ID:** identificador estable, por ejemplo `PAY-001`.
- **Nombre:** descripción corta.
- **Motivo:** por qué existe.
- **Alcance:** organización, sede, rol o módulo afectado.
- **Condición:** cuándo aplica.
- **Resultado esperado:** qué debe ocurrir.
- **Fuente de verdad:** servicio/capa donde se implementa principalmente.
- **Defensa adicional:** constraint, trigger u otra protección si existe.
- **Pruebas:** casos que demuestran la regla.

## Ejemplos genéricos

### PAY-001 — Evitar cobro activo duplicado

- Motivo: impedir duplicidad financiera accidental.
- Alcance: módulo de pagos.
- Condición: existe un pago activo para la misma obligación y periodo.
- Resultado esperado: rechazar un segundo pago activo.
- Fuente de verdad: servicio de pagos.
- Defensa adicional: restricción de integridad si el modelo lo permite.
- Pruebas: primer pago permitido; duplicado rechazado; comportamiento tras invalidación comprobado.

La identidad de la obligación debe usar el recurso exacto. No es suficiente comprobar que el actor tiene algún pago del mismo tipo si el pago pertenece a otro curso, reserva, factura, cita, periodo o recurso.

### TMP-001 — Derivar estados temporales desde fechas

- Motivo: impedir que un estado quede congelado por falta de una actualización manual.
- Alcance: entidades cuyo estado depende del paso del tiempo.
- Condición: existen fecha de inicio y fecha de fin.
- Resultado esperado: antes del inicio = futuro; dentro del rango inclusivo = activo; después del fin = terminado.
- Fuente de verdad: fechas + zona horaria operativa.
- Defensa adicional: reconciliación idempotente del estado persistido si el proyecto necesita almacenarlo.
- Pruebas: día anterior; día inicial; día final; día posterior; zona horaria correcta.

### TMP-002 — Aplicar cambios solo desde su fecha efectiva

- Motivo: evitar que un plan, membresía, tarifa, permiso o servicio futuro altere prematuramente el estado vigente o produzca deuda ficticia.
- Alcance: entidades con cambios programados por periodo o fecha efectiva.
- Condición: se registra un cambio cuyo inicio es posterior a la fecha operativa actual.
- Resultado esperado: conservar el valor vigente, guardar el valor futuro como programado y promoverlo únicamente al alcanzar `vigente_desde`.
- Fuente de verdad: valor actual + valor programado + fecha efectiva + periodo exacto de las obligaciones asociadas.
- Defensa adicional: promoción idempotente; validación transaccional; bloqueo de reescritura cuando una obligación ya tiene historial financiero.
- Pruebas: antes de la fecha efectiva; día de activación; pago anticipado del periodo futuro; cambio de periodo/ciclo; obligación sin historial reconciliable; obligación con historial protegida.

Reglas asociadas:

- `PROGRAMADO` o `FUTURE` no significa `PENDIENTE DE PAGO` ni `MOROSO`.
- Un pago anticipado no debe activar el servicio antes de su fecha efectiva.
- Una obligación futura pagada debe seguir identificada con su periodo futuro.
- Una obligación del periodo actual no debe inventarse si el servicio todavía no está vigente.
- Al mover una obligación entre periodos o ciclos, solo pueden reconciliarse automáticamente registros pendientes sin cobro ni pagos asociados.
- Si existe historial financiero, preservar la evidencia y exigir un flujo explícito de corrección/reversión en vez de sobrescribirla.

### VIEW-001 — Mantener consistencia entre vistas

- Motivo: evitar que dos pantallas representen de forma contradictoria el mismo estado de negocio.
- Alcance: listados, fichas, detalles, formularios y reportes que comparten una obligación/regla.
- Condición: dos o más superficies muestran o actúan sobre el mismo recurso.
- Resultado esperado: todas consumen la misma definición canónica.
- Fuente de verdad: servicio/consulta canónica de dominio.
- Defensa adicional: pruebas de regresión que cubran las superficies críticas.
- Pruebas: el mismo fixture produce el mismo estado en todas las vistas relevantes.

### AUTH-RO-001 — Consultas read-only sin escrituras ocultas

- Motivo: conservar la semántica y seguridad de los roles de consulta.
- Alcance: usuarios o procesos sin permiso de mutación.
- Condición: una acción está autorizada únicamente como lectura.
- Resultado esperado: la consulta no ejecuta reconciliaciones persistentes, housekeeping ni escrituras automáticas.
- Fuente de verdad: autorización del servidor.
- Defensa adicional: separar estado derivado de reconciliación persistida.
- Pruebas: lectura permitida sin mutaciones; escritura equivalente rechazada.

## Reglas de diseño

- No duplicar una misma regla con implementaciones contradictorias.
- Si una regla existe también en base de datos, documentar ambas capas.
- Los cambios de reglas financieras requieren pruebas de regresión.
- Las reglas de aislamiento y permisos requieren casos negativos.
- Las excepciones deben ser explícitas y justificadas.
- Los estados temporales deben usar una zona horaria operativa explícita.
- Los cambios futuros deben representarse como programados hasta su fecha efectiva; no deben sobrescribir prematuramente el estado actual.
- "Todavía no vigente" y "pendiente de pago" son estados distintos y deben representarse de forma distinta.
- El historial financiero existente debe considerarse evidencia protegida frente a reconciliaciones automáticas.
- Ocultar/deshabilitar una acción en UI mejora la UX, pero no sustituye la validación de servidor.
- Si un estado persistido puede quedar obsoleto por el paso del tiempo, las lecturas críticas deben poder derivarlo desde sus datos fuente.

## Catálogo por proyecto

Cada proyecto que use Hache-Base debe mantener su catálogo específico fuera del núcleo genérico. Hache-Base conserva el formato y los patrones; el negocio conserva sus decisiones.

Ver también `docs/ESTADOS-TEMPORALES-E-INTEGRIDAD.md`.
