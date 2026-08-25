# Tests

Estrategia base de pruebas para proyectos construidos sobre Hache-Base.

## Capas previstas

- `static/`: sintaxis, lint y regresiones estáticas.
- `smoke/`: comprobación rápida de rutas y flujos esenciales.
- `integration/`: base de datos, APIs e integraciones.
- `fixtures/`: datos aislados y desechables para pruebas.

## Regla

Los flujos críticos deben tener una comprobación automatizada antes de llegar a producción. Las pruebas con escritura no deben contaminar datos históricos reales.
