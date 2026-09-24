# Arquitectura de referencia

## Objetivo

Definir una arquitectura inicial para aplicaciones de servicios sin imponer reglas de un negocio concreto.

## Capas

### 1. Interfaz

- Sitio o portal público.
- Panel administrativo.
- Portal de usuario/cliente cuando corresponda.

La arquitectura visual de la interfaz sigue `Core → Theme → Extensions`. Core aporta estructura, accesibilidad, responsive, estados y tokens; Theme define identidad; Extensions resuelve necesidades específicas sin entrar al bundle base. Consultar `docs/design-system/ARCHITECTURE.md`.

La interfaz no debe decidir permisos por sí sola. Ocultar un botón no sustituye la autorización del servidor.

Cuando una acción ya es inválida según el estado canónico del dominio, la UI debe evitar ofrecerla para mejorar la experiencia, pero el servidor conserva la validación definitiva.

### 2. Aplicación

Los endpoints/controladores reciben la solicitud, validan el contexto y delegan la operación. Deben evitar contener consultas SQL complejas o reglas de negocio extensas.

### 3. Servicios de dominio

Contienen reglas reutilizables del caso de uso: alta, cambio de estado, cobro, agenda, etc. Deben recibir explícitamente el contexto de organización/sede cuando sea relevante.

Las reglas temporales deben recibir o resolver una zona horaria operativa explícita. Si varias vistas muestran el mismo estado, deben consumir la misma definición canónica de dominio.

### 4. Persistencia

Repositorios o componentes de acceso a datos encapsulan consultas y escrituras. Las restricciones críticas se refuerzan también en la base de datos cuando sea apropiado.

Un campo de estado derivable del reloj puede persistirse por rendimiento o compatibilidad, pero debe tratarse como una proyección sincronizable. La fuente de verdad permanece en los datos que permiten derivarlo y en la regla de dominio correspondiente.

### 5. Infraestructura e integraciones

Correo, n8n, APIs de terceros y mensajería viven fuera del dominio principal. Un fallo de una integración no debe comprometer la integridad del núcleo.

### Read models y proyecciones

Un dashboard, resumen, expediente o lista compuesta es un consumidor de autoridades de dominio, no otra autoridad. Debe declarar por bloque la fuente canónica, corte temporal, zona horaria, cobertura y la diferencia entre un valor medido, un valor no disponible y uno fuera de cobertura.

La composición read-only deriva en memoria y no llama rutas que puedan mutar como efecto lateral. Si necesita sincronizar, generar un snapshot o reconciliar persistentemente, esa acción vive en un caso de uso de escritura separado, con autorización, auditoría y pruebas propias. Consultar `templates/READ-MODEL-CONTRACT.md` y, cuando se use PHP, `src/common/ReadModelContract.php`.

## Flujo recomendado

`Solicitud -> autenticación -> contexto -> autorización -> validación -> servicio -> persistencia -> auditoría -> respuesta`

Para una lectura de estado temporal puede existir además una derivación sin escritura:

`Lectura -> contexto -> regla temporal -> estado efectivo -> respuesta`

Una reconciliación persistida es una operación distinta y requiere permiso de mutación.

## Reglas estructurales

- Configuración y secretos fuera del código.
- Una fuente clara para cada regla de negocio.
- IDs y relaciones validados en servidor.
- Cambios de estado sensibles dentro de transacciones cuando corresponda.
- Auditoría de mutaciones administrativas relevantes.
- Errores internos registrados pero no expuestos al cliente.
- Integraciones externas desacopladas.
- Pruebas alrededor de permisos, límites de contexto y operaciones críticas.
- Zona horaria operativa explícita para reglas basadas en fechas.
- Estados derivados y estados persistidos claramente diferenciados.
- Consistencia entre listados, fichas, detalles y formularios que representan el mismo recurso.
- Consultas read-only sin efectos secundarios de escritura.
- Proyecciones y métricas con autoridad, corte, cobertura y ausencia explícitos.

## Adaptación

Un proyecto pequeño puede implementar estas capas con una estructura sencilla sin frameworks adicionales. La separación es conceptual: Hache-Base busca responsabilidades claras, no complejidad por decoración.

Para reglas temporales y consistencia entre vistas, consultar `docs/ESTADOS-TEMPORALES-E-INTEGRIDAD.md`.
