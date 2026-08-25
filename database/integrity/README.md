# Patrones de integridad

Usar esta carpeta como referencia al diseñar módulos concretos.

## Herramientas

- **Foreign keys:** evitan referencias a entidades inexistentes.
- **Unique indexes:** evitan duplicados que nunca deberían coexistir.
- **Composite indexes:** ayudan a expresar unicidad dentro de una organización/sede/periodo.
- **CHECK constraints:** limitan estados o valores incompatibles cuando el motor los soporta.
- **Triggers:** última línea de defensa para relaciones que no pueden expresarse de forma simple con claves y constraints.

## Regla

Preferir la restricción más simple que exprese la invariancia. Un trigger no debe ser la primera opción si una foreign key o índice único resuelve el problema.

Las reglas críticas deben tener también pruebas de aplicación. La base de datos protege la integridad; no reemplaza la autorización del servidor.

## Multi-sede

Cuando dos entidades relacionadas deben pertenecer a la misma sede, la aplicación debe comprobarlo antes de escribir y la base puede añadir una defensa adicional cuando el modelo lo permita. Nunca confiar únicamente en un `site_id` enviado por el navegador.
