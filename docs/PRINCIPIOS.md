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

## Filosofía

Hache-Base no es un proyecto terminado que se clona y se renombra. Es una caja de herramientas y una arquitectura de referencia para construir proyectos nuevos con menos deuda técnica desde el primer día.
