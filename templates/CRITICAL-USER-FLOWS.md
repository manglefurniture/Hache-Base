# Critical User Flows — plantilla

Esta plantilla implementa el contrato documental de `GOV-001` a `GOV-004` del Production Readiness Standard.
No reemplaza las pruebas ni la evidencia del proyecto.

## 1. Identificación del proyecto

- Proyecto:
- Repositorio:
- Commit/artefacto evaluado:
- Entorno:
- Nivel declarado: A / B / C
- Justificación del nivel:
- Dueño técnico:
- Dueño de negocio:
- Fecha de revisión:

> Si una sola ruta o módulo cumple criterios de un nivel mayor, documentarlo y elevar ese flujo/módulo sin inflar innecesariamente el resto del proyecto.

## 2. Inventario de Critical User Flows

| CUF ID | Nombre | Nivel del flujo | Dueño técnico | Dueño negocio | Resultado autoritativo esperado | Estado |
| --- | --- | --- | --- | --- | --- | --- |
| CUF-001 |  | A/B/C |  |  |  | DRAFT |

Estados sugeridos del documento: `DRAFT`, `READY_FOR_TEST`, `VERIFIED`, `REVIEW_REQUIRED`.
No confundir estos estados documentales con estados de negocio de una operación asíncrona.

## 3. Ficha por CUF

### CUF-___ — Nombre

**Objetivo de negocio:**  
**Nivel:** A / B / C  
**Dueño técnico:**  
**Dueño de negocio:**

#### Precondiciones

- 

#### Pasos observables

1. 
2. 
3. 

#### Resultado correcto

- Resultado visible para usuario:
- Resultado autoritativo en servidor/datos:
- Estado terminal esperado:

#### Mutaciones y datos

- Datos leídos:
- Datos creados/modificados:
- Datos personales/sensibles:
- Constraints/transacciones relevantes:

#### Integraciones

| Integración | Propósito | Timeout | Retry | Confirmación autoritativa | Fallback/degradación |
| --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |

#### Estados de fallo

| Caso | Estado esperado | Mensaje/UX seguro | Retry permitido | Reconciliación/recuperación |
| --- | --- | --- | --- | --- |
| Timeout |  |  | Sí/No |  |
| Duplicado |  |  | Sí/No |  |
| Dependencia caída |  |  | Sí/No |  |
| Respuesta inválida |  |  | Sí/No |  |

#### Idempotencia y concurrencia

- ¿Puede repetirse la operación?: Sí / No
- Idempotency key / unique constraint / claim:
- Ventana de deduplicación:
- Comportamiento ante dos solicitudes concurrentes:
- Estado `UNKNOWN`/reconciliación cuando aplique:

#### Pruebas

- Unit:
- Integration:
- E2E:
- Casos de fallo:
- Duplicados/concurrencia (C cuando aplica):
- Fixture/datos aislados:

#### Smoke de release

- URL/comando:
- Resultado esperado:
- Marcador/body/version esperado:
- Evidencia:

#### Señales operativas

- `request_id`:
- `correlation_id` / business operation ID:
- Eventos/logs que reconstruyen el flujo:
- Métrica/alerta cuando aplica:

#### Recovery

- Qué puede reintentarse:
- Qué debe reconciliarse:
- Runbook:
- Criterio de rollback/bloqueo de mutaciones:
- Evidencia de recuperación:

## 4. Matriz CUF → evidencia

| CUF | Tests | Smoke | Logs/señales | Runbook | Evidencia vigente | Resultado |
| --- | --- | --- | --- | --- | --- | --- |
| CUF-001 |  |  |  |  |  | NOT EVALUATED |

Estados de evaluación permitidos por la norma: `PASS`, `FAIL`, `N/A`, `NOT EVALUATED`.
`NOT EVALUATED` nunca equivale a `PASS`; `N/A` siempre requiere justificación verificable.
