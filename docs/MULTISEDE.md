# Multiempresa y multisede

## Principio

La organización/sede no es solo un filtro visual. Es una frontera de autorización e integridad.

## Modelo conceptual

- `organizations`: empresa, cliente o tenant propietario del conjunto de datos.
- `sites`: sucursales, sedes, locales o centros pertenecientes a una organización.
- `users`: usuarios autenticados.
- `user_sites`: relación entre usuarios y sedes cuando un usuario puede operar en una o varias.

Un proyecto de una sola empresa puede omitir `organizations`. Un proyecto de una sola sede puede omitir `sites`, pero no debe simular multisede innecesariamente.

## Reglas

1. Toda entidad que pertenezca a una sede debe conservar `site_id` o una relación inequívoca hacia ella.
2. El servidor determina las sedes permitidas a partir de la sesión/identidad, nunca de un campo confiado del navegador.
3. Un ID válido no implica acceso autorizado.
4. Las consultas deben aplicar el alcance de organización/sede.
5. Las escrituras deben comprobar que todas las entidades relacionadas pertenecen al mismo contexto cuando la regla del negocio así lo exige.
6. Los administradores globales deben ser una capacidad explícita, no una excepción accidental.
7. Los reportes y operaciones financieras deben declarar el contexto que están agregando.

## Defensa en profundidad

Cuando sea razonable, usar claves foráneas, índices únicos compuestos, constraints o triggers para impedir relaciones que la aplicación nunca debería producir.

## Pruebas mínimas

- Usuario de sede A no puede leer datos exclusivos de sede B.
- Usuario de sede A no puede modificar datos de sede B usando IDs manuales.
- Una relación entre entidades de sedes incompatibles falla.
- Un usuario autorizado para varias sedes cambia de contexto de forma explícita.
- Los reportes no mezclan sedes salvo que el permiso y el caso de uso lo requieran.

## Anti-patrón

No implementar aislamiento únicamente con algo equivalente a `WHERE site_id = valor_enviado_por_el_cliente`. El contexto autorizado debe originarse en la identidad autenticada.
