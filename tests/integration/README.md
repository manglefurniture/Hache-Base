# Pruebas de integración

Cada proyecto debe añadir casos concretos para sus flujos críticos. La base exige cubrir, cuando apliquen:

- autenticación válida e inválida;
- permiso permitido y denegado;
- aislamiento entre sedes/organizaciones;
- escrituras con fixtures aislados;
- pagos, invalidaciones y recálculos financieros;
- migraciones sobre un clon/staging;
- endpoints internos con y sin Bearer token;
- integraciones externas sin mezclar secretos con fixtures.

## Regla de datos

Las pruebas con escritura no deben ejecutarse sobre datos históricos reales. Usar una base de staging, clon o fixtures desechables y verificar recuentos/estado antes y después cuando el flujo pueda afectar información existente.
