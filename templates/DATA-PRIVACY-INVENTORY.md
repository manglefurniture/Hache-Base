# Inventario de datos y privacidad — P1-09 / PRIV-001…PRIV-003

> Plantilla por proyecto para documentar datos personales, minimización, acceso, retención, eliminación/anonimización, terceros y analytics/cookies/trackers. Produce evidencia para revisión humana; **no** determina por sí sola una base legal, una jurisdicción aplicable ni cumplimiento normativo.

## 1. Metadatos y alcance

- Proyecto:
- Nivel Production Readiness: A / B / C
- Owner del inventario:
- Persona revisora:
- Jurisdicción(es) y mercados evaluados:
- Referencia a política/asesoría aplicable, si existe:
- Fecha de revisión (`YYYY-MM-DD`):
- Próxima revisión:
- Commit/build/entorno revisado:
- Estado: BORRADOR / REVISADO

### Aplicabilidad

- ¿El proyecto trata datos personales?: sí / no / por revisar
- ¿El proyecto trata categorías sensibles o de riesgo elevado según su contexto?: sí / no / por revisar
- ¿Existen analytics, cookies, pixels, SDKs o trackers?: sí / no / por revisar
- ¿Existen terceros que reciben datos?: sí / no / por revisar
- `THIRD-PARTY-INVENTORY.md` revisado y consistente: sí / no / no aplica

No usar `no` para cerrar un control sin evidencia. Si el proyecto afirma **NO_PERSONAL_DATA**, registrar:

- Declaración: `NO_PERSONAL_DATA`
- Superficies revisadas: browser / backend / DB / logs / correo / jobs / webhooks / analytics / backups / soporte / otras
- Evidencia de revisión (schema, formularios, network, configuración, logs de muestra sanitizados u otra):
- Persona revisora:
- Fecha (`YYYY-MM-DD`):

`NO_PERSONAL_DATA` no vuelve automáticamente N/A a `PRIV-003`: cookies/analytics/trackers se evalúan por separado cuando existen.

Si el proyecto afirma que no existen analytics/cookies/trackers, registrar un estado vacío verificable para `PRIV-003`:

- Declaración: `NO_TRACKERS`
- Alcance revisado: páginas/CUF, hosts/subdominios, browser storage, cookies HTTP, scripts/SDKs, tag managers, network requests y entornos incluidos
- Evidencia de scan/network/storage o inspección equivalente:
- Herramienta/procedimiento y versión, cuando aplique:
- Commit/build/entorno revisado:
- Persona revisora:
- Fecha (`YYYY-MM-DD`):

`NO_TRACKERS` es evidencia de un inventario vacío, no un PASS automático. Debe corresponder al alcance real revisado y volver a evaluarse si aparecen scripts, storage, cookies, SDKs, analytics o terceros nuevos.

## 2. Inventario de datos — PRIV-001

Usar IDs estables (`DATA-001`, `DATA-002`, …). Inventariar por campo o grupo homogéneo únicamente cuando finalidad, acceso, retención y eliminación sean realmente iguales.

| ID | Dato/categoría | Titular | Fuente | Finalidad concreta | Decisión/base por jurisdicción | Obligatorio/opcional | Sistema/ubicación | Terceros | Owner |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DATA-001 |  |  |  |  |  |  |  | TP-___ / ninguno |  |

### Ficha por dato o grupo

Duplicar por cada ID.

#### DATA-001 — <dato o grupo homogéneo>

- Nombre/categoría:
- Titular(es) de los datos:
- Fuente: proporcionado / observado / derivado / tercero / sistema
- Campo(s)/atributo(s) concretos:
- ¿Dato personal?: sí / no / por revisar
- ¿Categoría sensible/riesgo elevado en el contexto aplicable?: sí / no / por revisar
- Finalidad concreta:
- ¿Es necesario para esa finalidad?: sí / no / por revisar
- Obligatorio u opcional para el usuario/CUF:
- CUF/operación de negocio relacionada:
- Decisión/base/justificación por jurisdicción y referencia de aprobación:
- Sistema(s), tabla(s), storage o log donde existe:
- Réplicas/caches/índices/exports relevantes:
- Tercero(s) receptores por ID de `THIRD-PARTY-INVENTORY.md`: TP-___ / ninguno
- Roles/personas/sistemas con acceso:
- Cifrado en tránsito:
- Cifrado en reposo cuando riesgo/ley/política lo requiera:
- Regla de retención (duración **y evento de inicio**):
- Motivo de la retención:
- Mecanismo de eliminación/anonimización:
- Tratamiento en backups/snapshots:
- Canal/proceso de derechos aplicable:
- Owner:
- Evidencia/referencias:

No escribir valores personales reales en esta plantilla. Registrar estructura, categorías y evidencia sanitizada.

## 3. Minimización y acceso — PRIV-002

Para cada `DATA-*`, responder con evidencia:

- ¿Qué rompe si el campo no se recopila?:
- ¿Puede derivarse localmente o recopilarse más tarde?:
- ¿Se evita copiarlo a logs, analytics, URLs, nombres de archivo o metadata que no lo necesitan?:
- ¿Los formularios/API aceptan únicamente lo necesario?:
- ¿Los roles de lectura/modificación/eliminación son mínimos?:
- ¿Existen tests o revisión de autorización sobre el dato?:
- ¿Los entornos no productivos usan datos ficticios/sanitizados?:
- ¿Exports, soporte y herramientas administrativas tienen acceso explícito y auditable?:
- ¿La eliminación/anonimización puede ejecutarse sin corromper obligaciones históricas que deban conservarse?:

Un campo “útil por si acaso” no demuestra minimización. Un dato conservado por una obligación o riesgo real debe documentar la regla específica en vez de usar `indefinido` sin justificación.

## 4. Matriz de retención y eliminación

| Datos/ID | Sistema | Regla de retención | Inicio del plazo | Hold/excepción y dueño | Acción al vencer | Backups | Evidencia/drill | Owner |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DATA-001 |  |  |  |  | delete / anonymize / archive restringido |  |  |  |

### Contrato de retención

- La retención se expresa con **duración + evento de inicio**, no solo “30 días” o “mientras sea necesario”.
- Toda excepción/hold tiene causa, owner, fecha o criterio de revisión y alcance limitado.
- El mecanismo de expiración/eliminación/anonimización identifica qué pasa en DB primaria, replicas, search/index, objetos, caches y exports aplicables.
- Los backups documentan si la eliminación inmediata es técnicamente posible o si el dato desaparece al expirar el backup; restaurar un backup no debe reintroducir silenciosamente datos que ya debían permanecer eliminados sin un proceso de reconciliación.
- Registrar evidencia de ejecución o drill cuando el proyecto dependa de un proceso automático de retención.

Hache Base no fija un número universal de días. El plazo pertenece a la finalidad, riesgo, requisitos de negocio y jurisdicción del proyecto.

## 5. Canal y proceso de derechos — PRIV-001

Documentar solo los derechos/procesos que correspondan a la jurisdicción y política aplicables; no asumir desde Core un catálogo legal universal.

- Canal público/interno para solicitudes:
- Owner/equipo responsable:
- Cómo se verifica identidad de forma proporcional:
- Cómo se localizan los `DATA-*` y sistemas afectados:
- Operaciones soportadas cuando aplican: acceso / corrección / export / eliminación / oposición / restricción / otras
- Excepciones o datos que deben conservarse y referencia de aprobación:
- SLA/plazo aplicable y fuente:
- Evidencia de prueba del proceso:
- Registro/auditoría de la solicitud sin guardar contenido sensible innecesario:

## 6. Analytics, cookies y trackers — PRIV-003

Inventariar cookies HTTP, Web Storage, pixels, analytics, tag managers, SDKs de medición/ads y cualquier tracker equivalente. Usar IDs estables (`TRACK-001`, …). Una cookie técnica de sesión también se inventaría, aunque su tratamiento pueda ser distinto de un tracker de marketing.

| ID | Nombre/patrón | Tecnología | First/third party | Propósito | Datos/categorías | Duración | Tercero | Clasificación del proyecto | Activación |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TRACK-001 |  | cookie / localStorage / pixel / SDK / otro |  |  | DATA-___ / ninguno |  | TP-___ / ninguno | esencial / no esencial / por revisar |  |

### Ficha por tracker

- ID:
- Nombre/patrón:
- Provider/origen:
- Tecnología:
- Propósito:
- Datos enviados/leídos:
- `DATA-*` relacionado:
- `TP-*` relacionado:
- Duración/expiración:
- Clasificación y referencia de decisión por jurisdicción/política:
- Estado **antes de una decisión de consentimiento**, cuando aplica:
- Estado tras aceptar, cuando aplica:
- Estado tras rechazar, cuando aplica:
- Comportamiento al retirar/cambiar la decisión, cuando aplica:
- ¿Se carga código/red antes de lo permitido por la política definida?: sí / no / por revisar
- Evidencia de scan/network/storage:
- Owner:

No codificar en Core reglas como “todo analytics exige consentimiento” o “esta cookie siempre es esencial”. El proyecto define y aprueba la política aplicable; la evidencia debe demostrar que el runtime se comporta de acuerdo con esa decisión.

## 7. Consistencia con terceros

Para cada flujo de datos hacia un proveedor:

- el `DATA-*` referencia al `TP-*` correspondiente;
- `THIRD-PARTY-INVENTORY.md` describe propósito, datos compartidos, timeout/fallback, coste y retiro;
- este inventario describe finalidad, acceso, retención y decisión/base contextual del **dato**;
- si el proveedor añade subprocesadores/destinos relevantes para el proyecto, se registra la referencia que corresponda;
- eliminar un tercero exige revisar si quedan datos, credenciales, trackers, DNS/scripts/configuración o retención pendiente.

No duplicar listas divergentes: los IDs estables enlazan ambos inventarios.

## 8. Evidencia mínima por control

### PRIV-001 — cuando hay datos personales

La revisión debe poder demostrar:

- qué datos existen y para qué finalidad;
- decisión/base contextual por jurisdicción;
- qué terceros los reciben;
- dónde se almacenan;
- quién accede;
- cuánto tiempo se conservan y desde qué evento;
- cómo se eliminan/anonimizan;
- qué canal/proceso de derechos aplica.

### PRIV-002 — cuando hay datos personales

La revisión debe demostrar minimización por campo/grupo, acceso mínimo, protección en tránsito/reposo según riesgo/política y un proceso ejecutable de eliminación/anonimización. Una tabla completada sin pruebas de acceso/retención sigue siendo evidencia parcial.

### PRIV-003 — cuando existen analytics/cookies/trackers

La revisión debe demostrar inventario real y comportamiento observado de storage/network frente a la política de consentimiento/ley que el proyecto haya aprobado. `No hay banner` y `hay banner` no son por sí solos evidencia de cumplimiento.

Cuando la revisión concluya que no existen trackers, `NO_TRACKERS` debe aportar alcance, evidencia de scan/network/storage o inspección equivalente, commit/build/entorno, persona revisora y fecha. Un `no` sin esa evidencia permanece sin evaluar.

## 9. Cambios que obligan a re-evaluar

Revisar el inventario cuando cambie cualquiera de estos puntos:

- nuevo campo, formulario, API, upload o log con datos;
- nueva finalidad o reutilización de un dato existente;
- nuevo tercero/subprocesador o cambio material de datos compartidos;
- nuevo analytics/tag/SDK/cookie/tracker;
- cambio de jurisdicción/mercado/política aprobada;
- cambio de retención, backup, export, acceso administrativo o mecanismo de eliminación;
- incidente de privacidad/seguridad o hallazgo de datos fuera del inventario.

## 10. Guardrails

- No incluir valores personales reales, tokens, cookies de sesión reales, API keys ni secretos.
- No copiar una “base legal” genérica sin identificar jurisdicción, decisión y referencia de aprobación del proyecto.
- No asumir que cifrar un dato justifica recopilarlo o conservarlo.
- No convertir automáticamente `NO_PERSONAL_DATA` en PASS sin alcance y evidencia de revisión.
- No convertir automáticamente `NO_TRACKERS` en PASS sin alcance y evidencia verificable del inventario vacío.
- No convertir automáticamente este inventario en `PASS`; `PRIV-001…003` requieren evidencia del proyecto y revisión humana según el registro canónico.
- No usar P1-09 para imponer una CMP, proveedor de analytics, herramienta legal o política universal desde Core.
