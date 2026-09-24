# Contrato de Read Model, Métricas y Evidencia

> Plantilla opt-in para una vista, API, dashboard, resumen o collector que compone datos de varias autoridades. No crea tablas, snapshots, colas ni reglas de negocio. Tampoco convierte evidencia técnica en `PASS`.

## 1. Identificación

- Proyecto:
- Read model / endpoint:
- Dueño técnico:
- Dueño de negocio:
- Consumidores permitidos:
- Permiso y contexto de lectura:
- Commit/artefacto evaluado:

## 2. Autoridad y proyección

| Dato mostrado | Autoridad única | Regla/cálculo canónico | Consumidor/proyección | ¿La proyección escribe? |
| --- | --- | --- | --- | --- |
|  |  |  |  | No |

La proyección puede leer, filtrar y componer. No mantiene una segunda verdad de saldos, estados, asistencia, identidad, permisos ni otra regla de dominio. Si necesita sincronización persistida, se diseña como una mutación separada, autorizada, auditable y probada.

## 3. Contrato por métrica o bloque numérico

| ID | Autoridad | Numerador | Denominador | Exclusiones | Corte (`cutoff_at`) | Zona horaria | Cobertura | Disponibilidad | Valor/Unidad | Detalle reconciliable |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  |  |  | `no aplica` debe declararse así |  |  |  |  |  |  |  |

Cada consumidor usa esta definición; la UI no implementa una segunda fórmula. `0` solo significa cero cuando la autoridad y cobertura permiten medirlo. Para datos no disponibles, fuera de cobertura, no evaluados, no aplicables o con evidencia insuficiente, devolver `value=null` y el estado explícito; nunca un cero ni `PASS` implícito.

Si el proyecto usa PHP, `src/common/ReadModelContract.php` puede validar en la frontera los campos anteriores y preservar esta distinción sin calcular la métrica.

## 4. Cobertura e historia

Por cada bloque histórico declarar:

| Bloque | Estado (`complete` / `forward_only` / `out_of_coverage` / `not_evaluated`) | Inicio explícito de cobertura | `history_reconstructed` | Límite que ve el usuario |
| --- | --- | --- | --- | --- |
|  |  |  | `false` por defecto |  |

`forward_only` exige un marcador de inicio durable y no permite atribuir acciones previas que nunca se capturaron. Una corrección posterior conserva su propia fecha/evidencia; no reescribe una instantánea histórica existente ni finge un corte histórico que no fue guardado.

Para cada lectura elegir y etiquetar una semántica:

- **Viva/reconciliable:** refleja las autoridades actuales sobre hechos fechados; una corrección posterior puede cambiarla.
- **Snapshot histórico:** su significado y corte están preservados de forma durable; las correcciones posteriores se registran como hechos nuevos.

No llamar snapshot a una lectura viva ni recalcular silenciosamente un snapshot con reglas actuales.

## 5. Lectura, composición y pendientes de atención

- El endpoint/collector usa solo consultas read-only; una transacción read-only se usa cuando el motor la soporte y corresponda.
- No crea filas, promueve estados, reconcilia persistentemente, hace housekeeping, registra historial ni llama endpoints que puedan mutar como efecto lateral.
- El mismo `cutoff_at`, zona horaria y contexto autorizado viajan a cada bloque compuesto o sus diferencias quedan expuestas.
- La salida incluye solo agregados o detalles mínimos necesarios para reconciliar; no incluye credenciales, filas completas, secretos ni PII por defecto.

Si la proyección presenta asuntos que requieren atención, declarar por separado:

| Señal/caso | Registro causante | Regla de detección | Estado de atención | Quién/cuándo atendió | Evidencia de resolución |
| --- | --- | --- | --- | --- | --- |
|  |  |  | pendiente / atendido / resuelto |  |  |

Marcar un asunto como atendido solo describe la gestión. Nunca resuelve, paga, cancela, inscribe, bloquea ni modifica automáticamente el registro causante.

## 6. Evidencia operacional minimizada

| Collector | Entorno/fecha | Alcance | Read-only | Transacción read-only | PII minimizada | Reconciliación | Resultado técnico | Decisión humana |
| --- | --- | --- | --- | --- | --- | --- | --- |
|  |  |  | sí | completada / no aplica / no soportada | sí |  |  | `HUMAN_REVIEW_REQUIRED` |

El collector conserva observaciones agregadas y referencias de evidencia, no credenciales ni registros personales. Puede demostrar que una consulta se ejecutó y que sus agregados conciliaron; no se autodeclara `PASS`. Una persona responsable registra por separado la conclusión, fecha, entorno y límites residuales.

## 7. Regresiones del proyecto

- Caso disponible con valor positivo y con `0` real.
- Fuente sin evidencia/cobertura: `value=null`, estado explícito y nunca `0`/`PASS`.
- Periodo anterior al inicio `forward_only`: fuera de cobertura, sin backfill.
- Corrección posterior frente a lectura viva y frente a snapshot, cuando ambos existan.
- Consulta read-only sin mutaciones en las tablas observadas ni llamadas a rutas mutantes.
- Dos consumidores del mismo bloque reciben la misma definición/autoridad.
- Collector minimiza PII y termina en `HUMAN_REVIEW_REQUIRED`.

Los umbrales, fórmulas, entidades, tablas, permisos, retention, nombres de estados y decisión final siguen siendo propiedad del proyecto.
