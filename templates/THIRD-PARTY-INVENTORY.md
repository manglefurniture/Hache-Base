# Inventario de terceros — P1-05 / PERF-010

> Completar por proyecto cuando exista cualquier tercero que participe en un Critical User Flow (CUF), procese/reciba datos, cargue recursos o añada coste de red/CPU/latencia. Este inventario produce evidencia para revisión; **no** aprueba automáticamente `PERF-010`, privacidad, seguridad ni cumplimiento legal.

## 1. Metadatos del inventario

- Proyecto:
- Nivel Production Readiness: A / B / C
- Owner del inventario:
- Persona revisora:
- Fecha de revisión (`YYYY-MM-DD`):
- Próxima revisión:
- Commit/build/entorno usado para las mediciones:
- Estado: BORRADOR / REVISADO

## 2. Qué cuenta como tercero

Registrar cualquier servicio, SDK, script, API, origen o recurso operado fuera del control directo del proyecto cuando pueda afectar comportamiento, datos o performance. Ejemplos: analytics/RUM, pixels/tags, CAPTCHA, mapas, chat, video, webfonts/CDN remotos, pagos, correo, mensajería, IA, storage externo, APIs de negocio y scripts/assets cargados desde otro origen.

No registrar librerías vendorizadas únicamente como “tercero runtime” por existir en dependencias; su riesgo de supply chain pertenece al control correspondiente. Sí registrar un proveedor cuando el producto en ejecución llama su servicio, carga sus recursos o comparte datos con él.

## 3. Estado cero — no hay terceros

No dejar la tabla vacía como evidencia implícita. Si el proyecto afirma que **no existen terceros**, completar:

- Declaración: `NO_THIRD_PARTIES`
- Alcance revisado: navegador / backend / jobs / webhooks / assets / infraestructura aplicable
- Evidencia de revisión (por ejemplo waterfall, configuración, código o inventario de egress):
- Persona revisora:
- Fecha (`YYYY-MM-DD`):

Una declaración de estado cero sin alcance, evidencia, revisor y fecha permanece **NOT EVALUATED**.

## 4. Resumen

| ID estable | Proveedor / servicio | Categoría | Owner | Propósito / CUF | Browser / server | Camino crítico | Estado |
| --- | --- | --- | --- | --- | --- | --- | --- |
| TP-001 |  |  |  |  |  | sí / no | planned / active / retiring |

Usar un ID estable por integración lógica. Si un mismo proveedor sirve a finalidades con datos, fallback o coste distintos, separarlas cuando eso mejore la trazabilidad.

## 5. Registro por tercero

Duplicar esta sección por cada ID del resumen.

### TP-001 — <proveedor / servicio>

#### Identidad y ownership

- ID estable: `TP-001`
- Proveedor / servicio:
- Categoría:
- Estado: planned / active / retiring
- Owner técnico/negocio:
- Propósito concreto:
- CUF/plantillas afectados:
- Superficie: browser / server / ambos / job / webhook
- ¿Está en camino crítico?: sí / no
- Endpoint/origen de referencia (sin credenciales ni query sensible):
- Config/secret reference: nombre de variable o secret manager **sin copiar valores secretos**

#### Datos compartidos

- Dirección: proyecto→tercero / tercero→proyecto / bidireccional
- Categorías de datos enviados:
- Categorías de datos recibidos:
- ¿Incluye datos personales o de negocio sensibles?: sí / no / por revisar
- Referencia a revisión de privacidad/seguridad, si aplica:

Describir categorías, no valores reales. Este campo no sustituye el inventario de privacidad ni decide por sí mismo una base legal.

#### Timeout, retry y fallback

- Timeout de conexión, si aplica:
- Timeout total/read, si aplica:
- Presupuesto de carga en navegador, si aplica:
- Retry/backoff:
- Requisito de idempotencia, si aplica:
- Fallback/degradación cuando falla o excede timeout:
- Impacto sobre el CUF si el fallback también falla:
- Kill switch / forma de desactivarlo:

Usar `N/A — <justificación>` cuando una dimensión realmente no aplique. Un `N/A` vacío no cierra el campo.

#### Coste de performance medido

- Fecha y build de medición:
- Entorno/dispositivo/perfil:
- Método y evidencia (waterfall, Lighthouse, RUM, trace, benchmark u otro):
- Comparación **con tercero**:
- Comparación **sin tercero** o baseline equivalente:
- Requests añadidos, si aplica:
- Transferencia añadida (bytes comprimidos), si aplica:
- JS/CSS o trabajo de main thread añadido, si aplica:
- Delta LCP / INP / CLS / TBT, si aplica:
- Latencia backend p50/p95 o tiempo añadido al CUF, si aplica:
- Resultado / observación:

No inventar un score único. Medir lo que el tercero realmente afecta. Para una API solo-servidor puede ser correcto documentar latencia/timeout y marcar métricas de navegador como `N/A — no participa en browser`. Para un script de navegador, una cifra de latencia backend por sí sola no representa su coste.

Si no es posible hacer una prueba con/sin tercero, documentar el baseline alternativo, la limitación y por qué la evidencia sigue siendo útil. “Sin medición” no equivale a coste cero.

#### Retiro y revisión

- Criterio de retiro/reemplazo:
- Alternativa/fallback estratégico, si existe:
- Señal que obliga a re-evaluar (coste, incidentes, cambio de datos, SLA, deprecación, etc.):
- Última revisión (`YYYY-MM-DD`):
- Evidencia/referencias:

## 6. Criterio de completitud

Para cada tercero `planned` o `active`, la revisión debe poder responder con evidencia:

- quién es el **owner**;
- cuál es el **propósito** y qué CUF toca;
- qué **datos compartidos** existen y en qué dirección;
- qué **timeout** o presupuesto temporal limita su impacto;
- cuál es el **fallback/degradación**;
- cuál es su **coste de performance medido** y cómo se comparó con/sin tercero o baseline equivalente;
- cuál es el **criterio de retiro**;
- cuándo y por quién se revisó.

Si falta una de esas piezas, el inventario no debe presentarse como evidencia completa de `PERF-010`.

## 7. Guardrails

- No guardar tokens, API keys, passwords, cookies ni secretos en este archivo; solo referencias de configuración.
- No declarar un proveedor “aprobado”, “seguro” o “legal” por aparecer en el inventario.
- No asumir que un tercero es aceptable porque el coste actual sea pequeño.
- No convertir automáticamente el inventario en `PASS`; `PERF-010` requiere revisión humana y medición del proyecto.
- Actualizar el registro cuando cambien finalidad, datos, origen/endpoint, SDK, comportamiento, coste, timeout, fallback o estrategia de retiro.
- Si P1-04 RUM usa un collector/SDK externo, registrarlo aquí como cualquier otro tercero.
