# Principios de Hache-Base

## Qué debe entrar

Hache-Base acepta componentes que sean reutilizables entre distintos tipos de negocio, por ejemplo:

- autenticación y autorización;
- roles y permisos;
- aislamiento por organización o sede;
- configuración por entorno;
- respuestas y protección de APIs;
- auditoría de mutaciones;
- migraciones y controles de integridad;
- utilidades genéricas;
- estados temporales derivados y zona horaria operativa;
- consistencia de reglas entre vistas, APIs y acciones;
- pruebas y fixtures;
- backup, despliegue, health checks y rollback;
- patrones seguros de integración externa.

## Qué no debe entrar

No se incorporará directamente:

- información real de alumnos, clientes o usuarios;
- nombres, precios o reglas exclusivas de Hache Natación;
- credenciales, tokens, claves SSH o contraseñas;
- dumps de producción;
- workflows específicos de Sharky o WhatsApp;
- lógica que solo tenga sentido para natación, salvo que primero sea generalizada.

## Regla de extracción

Un componente procedente de otro proyecto debe pasar por este proceso:

1. Identificar la responsabilidad genérica.
2. Eliminar nombres y datos específicos del negocio.
3. Convertir valores variables en configuración.
4. Documentar dependencias y supuestos.
5. Añadir una prueba o procedimiento de verificación cuando corresponda.
6. Incorporarlo mediante un cambio pequeño y trazable.

## Principios de integridad

- Una regla de negocio debe tener una definición canónica aunque se muestre en varias pantallas.
- Un estado que depende únicamente de fechas debe poder derivarse de sus datos fuente; si además se persiste, el valor guardado se considera una proyección sincronizable.
- Toda lógica basada en `hoy` debe usar una zona horaria operativa explícita, no la zona implícita del servidor.
- Una UI puede prevenir acciones inválidas, pero la validación definitiva permanece en servidor y, cuando corresponde, en una protección transaccional o de integridad.
- Un rol de solo lectura no debe provocar escrituras ocultas como efecto secundario de consultar una pantalla.
- Si un dato participó en un cierre, factura, corte, conciliación o snapshot histórico, una operación posterior no debe destruir la evidencia necesaria para explicar ese resultado. Invalidar no equivale automáticamente a borrar.
- Cuando dos eventos con precisión temporal insuficiente puedan haber ocurrido en distinto orden, una decisión que afecte trazabilidad histórica debe optar por la interpretación conservadora salvo que exista una fuente fiable de orden.
- Una acción asíncrona sensible debe capturar la identidad completa de su objetivo antes del primer `await`, mantener una identidad o bloqueo de operación en vuelo y evitar que respuestas antiguas modifiquen una interfaz que ya representa otra operación.

## Principios de cambio y revisión

- CI verde y revisión de código son capas diferentes: ambas deben satisfacerse según el riesgo del proyecto.
- Un hallazgo concreto debe producir una corrección concreta y proporcional; no convertir automáticamente un fix en auditoría o refactor general.
- No marcar como resuelto un hallazgo solo por conveniencia administrativa: primero confirmar su resolución material en el código actual.
- Una corrección que revele un nuevo caso límite genera un hallazgo nuevo; no queda cubierto por el cierre del hallazgo original.

## Filosofía

Hache-Base no es un proyecto terminado que se clona y se renombra. Es una caja de herramientas y una arquitectura de referencia para construir proyectos nuevos con menos deuda técnica desde el primer día.
