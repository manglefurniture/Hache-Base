# Entornos

Hache-Base separa `development`, `staging` y `production`.

## Development

Trabajo local. Puede usar fixtures y datos ficticios. Nunca debe necesitar secretos de producción.

## Staging

Es el lugar para probar migraciones, roles, sedes, integraciones y smoke tests antes de producción.

Debe usar:

- configuración independiente;
- base independiente;
- estructura equivalente a producción cuando sea posible;
- datos ficticios o una copia anonimizada;
- tokens y credenciales propios;
- dominio/subdominio distinto.

No reutilizar tokens de producción únicamente por comodidad.

## Production

Solo recibe cambios que pasaron preflight, pruebas y staging según el riesgo. Los despliegues deben tener backup y rollback disponibles.

## Copias de datos

Si una copia de producción se usa para diagnóstico/staging, anonimizar datos personales antes de exponerla fuera de su entorno protegido. La estrategia concreta depende del esquema del proyecto y debe documentarse allí; Hache-Base no incluye una rutina universal de anonimización que pueda borrar o alterar datos incorrectamente.

## Promoción

`development -> pull request/CI -> staging -> aprobación -> backup -> production -> health/smoke checks`
