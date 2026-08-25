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

## Ejemplo genérico

### PAY-001 — Evitar cobro activo duplicado

- Motivo: impedir duplicidad financiera accidental.
- Alcance: módulo de pagos.
- Condición: existe un pago activo para la misma obligación y periodo.
- Resultado esperado: rechazar un segundo pago activo.
- Fuente de verdad: servicio de pagos.
- Defensa adicional: restricción de integridad si el modelo lo permite.
- Pruebas: primer pago permitido; duplicado rechazado; comportamiento tras invalidación comprobado.

## Reglas de diseño

- No duplicar una misma regla con implementaciones contradictorias.
- Si una regla existe también en base de datos, documentar ambas capas.
- Los cambios de reglas financieras requieren pruebas de regresión.
- Las reglas de aislamiento y permisos requieren casos negativos.
- Las excepciones deben ser explícitas y justificadas.

## Catálogo por proyecto

Cada proyecto que use Hache-Base debe mantener su catálogo específico fuera del núcleo genérico. Hache-Base conserva el formato y los patrones; el negocio conserva sus decisiones.
