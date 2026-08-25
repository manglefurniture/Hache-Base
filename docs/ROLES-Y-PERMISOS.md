# Roles y permisos

## Regla principal

Definir permisos antes de construir las pantallas principales.

## Modelo recomendado

Separar tres conceptos:

- **Rol:** agrupación administrativa de capacidades.
- **Permiso:** acción concreta que puede realizarse.
- **Contexto:** organización, sede y/o recurso sobre el que puede realizarse.

Ejemplo conceptual: `payments.create` puede estar permitido para un rol en una sede y prohibido en otra.

## Roles base de referencia

Los nombres son configurables y no obligatorios:

- `SUPER_ADMIN`: administración global de la instalación cuando exista esa necesidad.
- `ADMIN`: administración dentro de su organización/contexto autorizado.
- `OPERATOR`: operaciones limitadas sin privilegios financieros o estructurales por defecto.
- `USER`: acceso a sus propios datos y operaciones permitidas.

No asumir que estos cuatro roles sirven para todos los proyectos. El proyecto debe crear su propia matriz.

## Matriz inicial

| Capacidad | SUPER_ADMIN | ADMIN | OPERATOR | USER |
| --- | --- | --- | --- | --- |
| Ver contexto propio | Sí | Sí | Sí | Sí |
| Gestionar usuarios | Configurable | Configurable | No | No |
| Cambiar configuración estructural | Configurable | Configurable | No | No |
| Registrar operaciones | Sí | Sí | Configurable | Solo propias si aplica |
| Operaciones financieras | Sí | Configurable | No por defecto | No por defecto |
| Ver otras sedes | Configurable | Según alcance | Según alcance | No por defecto |

La tabla es un punto de partida, no autorización ejecutable.

## Reglas de implementación

1. Autorizar en servidor en cada operación sensible.
2. No usar nombres de menú o visibilidad de UI como control de acceso.
3. Comprobar permiso y contexto del recurso.
4. Evitar condicionales de rol dispersos; centralizar decisiones repetidas.
5. Denegar por defecto cuando no exista una regla explícita.
6. Auditar cambios administrativos y financieros relevantes.
7. Probar intentos permitidos y prohibidos.

## Checklist por endpoint

- ¿Requiere autenticación?
- ¿Qué permiso requiere?
- ¿Cuál es el contexto autorizado?
- ¿El recurso solicitado pertenece a ese contexto?
- ¿El usuario puede actuar sobre sí mismo, terceros o ambos?
- ¿La acción debe auditarse?
- ¿Qué respuesta recibe un acceso denegado sin filtrar información?
