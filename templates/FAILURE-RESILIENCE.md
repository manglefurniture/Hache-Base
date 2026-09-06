# Failure Resilience — plantilla P2-03

> Adopción por proyecto de failure fixtures para `timeout`, HTTP `429`, HTTP `5xx`, DNS y storage. Los fixtures son **solo de test**: no activan chaos/fault injection en producción y no convierten controles `ROB-*` en PASS.

## 1. Proyecto y alcance

- Proyecto:
- Nivel A/B/C:
- Owner:
- Fecha de revisión:
- CUF/integraciones cubiertos:
- Adaptadores bajo prueba:

## 2. Regla principal

Un fallo de dependencia no autoriza automáticamente un retry.

Antes de decidir retry/reconcile/final failure, el proyecto debe conocer:

- si la operación es idempotente o tiene idempotency key/claim estable;
- si el resultado externo es autoritativo o quedó ambiguo;
- si existe consulta/reconciliación del recurso externo;
- límite de intentos, backoff+jitter y `Retry-After` cuando aplique;
- timeout de conexión y operación, con cancelación cuando el stack lo soporte;
- qué estado local puede mutar antes/después del fallo;
- qué evidencia demuestra que no se duplican efectos.

Cuando una operación asíncrona quede ambigua, el proyecto puede mapearla a los primitives existentes como `OUTCOME_UNKNOWN` / `RECONCILING` de `AsyncOperationState`, pero esa decisión no es universal y debe probarse en el CUF real.

## 3. Fixture reusable

Hache Base incluye:

`tests/fixtures/failures/FailureFixture.php`

El harness es determinista y no realiza red, DNS, storage ni `sleep`. Cada intento puede:

- lanzar un `FailureFixtureException` con metadata estable; o
- dejar ejecutar la operación simulada.

La metadata describe **qué falló** (`category`, `phase`, HTTP status y `retry_after_seconds` cuando aplica). Deliberadamente no incluye `should_retry`, estado final ni política de negocio.

Ejemplo:

```php
$fixture = FailureFixture::failOnce(FailureFixtureException::http429(30));

try {
    $fixture->invoke(fn () => $adapter->send($request));
} catch (FailureFixtureException $failure) {
    // El test del proyecto decide qué debe hacer SU adapter/CUF.
    assert($failure->httpStatus() === 429);
    assert($failure->retryAfterSeconds() === 30);
}
```

## 4. Matriz mínima

| Escenario | Fixture | Qué debe decidir/probar el proyecto | Evidencia mínima |
| --- | --- | --- | --- |
| Timeout | `FailureFixtureException::timeout()` | Timeout finito; outcome conocido vs ambiguo; cancelación; no retry ciego si puede duplicar efecto. | Test de timeout + estado/reconcile esperado. |
| HTTP 429 | `http429(seconds)` | Respetar `Retry-After` cuando corresponda; retry limitado y solo si es seguro. | Test de límite + metadata `Retry-After` + no duplicación. |
| HTTP 5xx | `http5xx(status)` | Distinguir fallo temporal/ambiguo; bounded retry o reconciliación según semántica real. | Test 5xx + límite/backoff o reconcile. |
| DNS | `dns()` | Ruta de error/fallback cuando no puede resolverse dependencia; no asumir entrega. | Test del adapter/fallback y error observable. |
| Storage | `storage()` | Qué ocurre si read/write falla; evitar corrupción/estado parcial; rollback/reconcile si aplica. | Test de integridad/atomicidad o comportamiento documentado. |

## 5. Timeout

Documentar por cada llamada externa:

- connect timeout:
- operation/read timeout:
- cancelación disponible:
- estado local antes de llamar:
- cómo se clasifica un timeout después de enviar la petición:
- mecanismo para consultar/reconciliar resultado ambiguo:

La prueba no debe usar un `sleep` largo para “simular” timeout. Usar el fixture para provocar la rama de error de forma inmediata y reproducible.

## 6. Retry / 429 / 5xx

- máximo de intentos:
- backoff:
- jitter:
- política `Retry-After`:
- códigos/errores reintentables:
- códigos/errores finales:
- idempotency key / constraint / claim:
- reconciliación previa/posterior:

Probar al menos:

1. fallo temporal seguido de éxito;
2. fallos repetidos hasta alcanzar el límite;
3. operación no idempotente donde un resultado ambiguo **no** genera efecto duplicado;
4. `429` con `Retry-After` conservado por el adapter/policy;
5. `5xx` según la semántica real del proveedor, sin asumir que todos significan lo mismo.

## 7. DNS y dependencia inaccesible

- error que expone el adapter internamente:
- mensaje público/fallback:
- logging/metric/trace sin PII/secrets:
- si existe proveedor alterno:
- quién decide failover:
- cómo se evita confundir “no conectó” con “operación confirmada”:

## 8. Storage

Definir por operación crítica:

- read/write implicado:
- frontera transaccional/atómica:
- qué sucede ante error antes del commit:
- qué sucede ante error después de una confirmación externa:
- cleanup/reconcile:
- cómo se detecta estado parcial:

El fixture de Base no abre archivos ni bases de datos. El proyecto debe envolver su adapter/repositorio testeable y demostrar su propia semántica.

## 9. Observabilidad del fallo

Para cada escenario comprobar, cuando aplique:

- request/correlation/trace ID preservado;
- evento/metric de baja cardinalidad;
- sin payloads, secretos ni PII;
- alerta/runbook si el escenario cruza un threshold accionable definido en P2-02;
- el fallo del sistema de observabilidad no cambia el resultado del CUF.

## 10. Evidencia

| CUF / adapter | timeout | 429 | 5xx | DNS | storage | retry límite | idempotencia/reconcile | Resultado |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |  |  | NOT EVALUATED |

Adjuntar:

- tests/commands ejecutados:
- CI run:
- configuración de timeout/retry versionada:
- evidencia de idempotencia/reconciliación:
- revisión humana:

## 11. Estado

- `NOT EVALUATED` / `PARTIAL` / `PASS` / `N/A`:
- justificación:
- pendientes:

P2-03 en Base valida que existen fixtures reproducibles para las cinco familias de fallo. La resiliencia real sigue siendo responsabilidad del adapter/CUF y de su evidencia de proyecto.
