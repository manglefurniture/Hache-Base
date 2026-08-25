# Arquitectura de referencia

## Objetivo

Definir una arquitectura inicial para aplicaciones de servicios sin imponer reglas de un negocio concreto.

## Capas

### 1. Interfaz

- Sitio o portal público.
- Panel administrativo.
- Portal de usuario/cliente cuando corresponda.

La interfaz no debe decidir permisos por sí sola. Ocultar un botón no sustituye la autorización del servidor.

### 2. Aplicación

Los endpoints/controladores reciben la solicitud, validan el contexto y delegan la operación. Deben evitar contener consultas SQL complejas o reglas de negocio extensas.

### 3. Servicios de dominio

Contienen reglas reutilizables del caso de uso: alta, cambio de estado, cobro, agenda, etc. Deben recibir explícitamente el contexto de organización/sede cuando sea relevante.

### 4. Persistencia

Repositorios o componentes de acceso a datos encapsulan consultas y escrituras. Las restricciones críticas se refuerzan también en la base de datos cuando sea apropiado.

### 5. Infraestructura e integraciones

Correo, n8n, APIs de terceros y mensajería viven fuera del dominio principal. Un fallo de una integración no debe comprometer la integridad del núcleo.

## Flujo recomendado

`Solicitud -> autenticación -> contexto -> autorización -> validación -> servicio -> persistencia -> auditoría -> respuesta`

## Reglas estructurales

- Configuración y secretos fuera del código.
- Una fuente clara para cada regla de negocio.
- IDs y relaciones validados en servidor.
- Cambios de estado sensibles dentro de transacciones cuando corresponda.
- Auditoría de mutaciones administrativas relevantes.
- Errores internos registrados pero no expuestos al cliente.
- Integraciones externas desacopladas.
- Pruebas alrededor de permisos, límites de contexto y operaciones críticas.

## Adaptación

Un proyecto pequeño puede implementar estas capas con una estructura sencilla sin frameworks adicionales. La separación es conceptual: Hache-Base busca responsabilidades claras, no complejidad por decoración.
