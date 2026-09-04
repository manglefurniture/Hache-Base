# Política de caché — P1-06 / PERF-011

> Completar por proyecto antes de producción. Esta plantilla define cómo decidir caché por tipo de respuesta y cómo demostrar invalidación. **No** convierte `PERF-011` en `PASS` por sí sola: la evidencia autoritativa son los headers reales del entorno desplegado y una prueba de invalidación/revalidación.

## 1. Metadatos

- Proyecto:
- Entorno:
- Owner de caché/CDN/proxy:
- Persona revisora:
- Fecha (`YYYY-MM-DD`):
- Commit/build evaluado:
- CDN/proxy/cache intermedio usado, si aplica:
- Estado: BORRADOR / REVISADO

## 2. Matriz obligatoria por tipo

No usar una política global única. Completar cada fila que aplique y marcar `N/A — <justificación>` cuando realmente no exista esa superficie.

| Tipo de respuesta | Ejemplos/rutas | Datos privados | `Cache-Control` final esperado | TTL / revalidación | Validator (`ETag` / `Last-Modified`) | `Vary` / cache key | Invalidation / purge | Evidencia |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| HTML público mutable |  | no |  |  |  |  |  |  |
| Asset con hash de contenido |  | no |  |  |  |  |  |  |
| Asset sin versionar |  | no |  |  |  |  |  |  |
| API pública |  | no |  |  |  |  |  |  |
| HTML/API autenticada o privada |  | sí |  |  |  |  |  |  |
| 4xx |  | depende |  |  |  |  |  |  |
| 5xx |  | no debe exponer datos |  |  |  |  |  |  |

## 3. Reglas mínimas

### HTML público mutable

- Definir explícitamente si usa `no-cache`, un TTL corto, `stale-while-revalidate` u otra estrategia.
- Si el mismo URL puede cambiar, documentar cómo el cliente/cache detecta la nueva versión: validator, purge, revalidación o expiración.
- `no-cache` **permite almacenar pero obliga a revalidar** antes de reutilizar; no confundirlo con `no-store`.
- El deploy debe tener un mecanismo de invalidación compatible con la política elegida.

### Assets con hash de contenido

- `immutable` solo aplica cuando el nombre/URL cambia al cambiar los bytes del recurso.
- Un asset realmente content-hashed puede usar caché pública de larga duración porque la invalidación ocurre mediante un URL nuevo.
- No reutilizar el mismo hash/nombre para contenido diferente.
- No depender de purgar un asset marcado `immutable` como flujo normal de deploy.

### Assets sin versionar

- No marcarlos `immutable` si el contenido puede cambiar conservando el mismo URL.
- Definir revalidación, TTL o purge explícitos.

### API pública

- Cachear solo representaciones realmente públicas y para las que exista una tolerancia de staleness documentada.
- Definir qué forma parte de la cache key: path, query permitida, headers relevantes y cualquier dimensión indicada en `Vary`.
- Una respuesta que dependa de identidad, autorización, cookie, tenant o datos personales no se convierte en pública por conveniencia de performance.

### HTML/API privada o autenticada

- Debe existir una política explícita que impida almacenamiento accidental en caches compartidos.
- El baseline conservador para respuestas sensibles es `Cache-Control: private, no-store, max-age=0` o una política equivalente demostrablemente segura.
- Si se permite caché privada del navegador para un caso concreto, documentar el motivo, el alcance, la expiración y por qué no filtra datos entre identidades.

### Errores

- 5xx y errores que puedan contener estado sensible deben ser `no-store` salvo justificación extraordinaria.
- 4xx son `no-store` por defecto. Si un 404 público se cachea deliberadamente, documentar TTL corto, invalidación y riesgo de ocultar una ruta recién publicada.
- Nunca cachear por accidente una respuesta de error generada durante un fallo temporal de origen.

## 4. Vary, cookies y autorización

- Documentar todos los headers que alteren la representación y deban formar parte de la cache key.
- Evitar `Vary` de cardinalidad alta o valores controlados por usuario sin necesidad.
- Revisar rutas que emiten `Set-Cookie` y rutas que aceptan `Authorization` antes de permitir caché compartida.
- La política observada después de Nginx/CDN/proxy es la evidencia final; un header correcto en PHP no basta si otra capa lo reemplaza.

## 5. Prueba de invalidación

Para cada tipo cacheable, registrar al menos un drill reproducible:

### Recurso mutable en el mismo URL

1. pedir versión A y registrar `Cache-Control`, validator y cuerpo/hash;
2. confirmar que una revalidación con validator vigente puede producir `304` cuando corresponda;
3. desplegar o simular versión B **en el mismo URL**;
4. repetir con el validator anterior;
5. confirmar que la respuesta ya no reutiliza A y entrega B/validator nuevo o que el purge/TTL definido fuerza el cambio;
6. registrar tiempos, CDN/proxy involucrado y evidencia.

### Asset content-hashed

1. registrar URL/hash A y headers;
2. cambiar los bytes del asset;
3. confirmar que el build genera URL/hash B distinto;
4. verificar que HTML/manifiesto referencia B;
5. comprobar que A puede permanecer cacheado sin afectar el release porque ningún consumidor nuevo depende de ese URL.

Si el proyecto usa purge explícito, registrar el comando/API/owner, alcance, tiempo de propagación y rollback.

## 6. Evidencia mínima de `PERF-011`

La revisión debe incluir:

- matriz completada para HTML, assets, API pública, privada y errores que existan;
- headers reales del entorno desplegado;
- evidencia de que respuestas sensibles no quedan en caché compartida;
- prueba de invalidación o revalidación para al menos un recurso mutable representativo;
- prueba de cambio de URL/hash para assets `immutable` si existen;
- comportamiento observado a través de CDN/proxy, no solo del runtime de aplicación;
- owner y procedimiento de corrección/rollback si una política de caché sale mal.

## 7. Guardrails

- No copiar TTLs del fixture de Hache Base como valores universales; cada proyecto justifica sus tiempos.
- No usar `public` en respuestas con datos personales, sesión o autorización sin una revisión específica que demuestre seguridad de la cache key y del almacenamiento.
- No usar `immutable` para URLs cuyo contenido pueda cambiar.
- No interpretar ausencia de header como una política válida.
- No declarar `PERF-011` aprobado sin headers reales e invalidación probada.
- Cambios de caché que alteren TTL, key, `Vary`, validators, purge o versionado requieren revisión coordinada con el mecanismo de deploy/rollback.
