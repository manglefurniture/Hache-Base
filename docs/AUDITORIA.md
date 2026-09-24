# Auditoría de mutaciones

## Propósito

Registrar cambios relevantes para poder responder: **quién cambió qué, cuándo, desde dónde y en qué contexto**.

Una mutación es una operación que crea, modifica, invalida, elimina o cambia el estado de información relevante. Consultar una pantalla normalmente no es una mutación.

## Qué registrar

Priorizar:

- cambios administrativos;
- pagos, invalidaciones y ajustes financieros;
- cambios de permisos o roles;
- altas, bajas y cambios de estado importantes;
- cambios de sede/organización;
- modificaciones de configuración;
- acciones relevantes ejecutadas por automatizaciones.

No convertir la auditoría en un log de absolutamente todo.

## Campos

`actor_type` permite distinguir `user`, `automation`, `system` u otros actores. `actor_id` y `actor_role` identifican al responsable cuando exista. `organization_id` y `site_id` conservan contexto. `action`, `entity_type` y `entity_id` describen la mutación. `before_data` y `after_data` son opcionales. `source`, `request_id`, `ip_address` y `metadata` ayudan a investigar el origen.

Para un cambio de dominio confirmado, identificar la entidad exacta y conservar actor/contexto cuando estén disponibles. No inventar un actor o un valor anterior ausente: conservar `null` y su límite explícito es mejor que reconstruirlo desde el presente.

## Eventos confirmados, resultados técnicos y no-ops

`AuditLogger` distingue dos clases mediante `event_kind`:

- `domain_change` (default compatible): se registra únicamente después de confirmar la mutación; incluye `entity_id` cuando la entidad tiene una referencia durable y descarta snapshots equivalentes, incluso si cambió el orden de sus claves.
- `technical_result`: puede documentar un resultado técnico separado, pero no acepta snapshots `before`/`after`; un HTTP 2xx no demuestra por sí mismo un cambio de dominio.

El helper descarta scopes distintos de `administrative`, como `diagnostic`, `telemetry` o `read_only`. Esos datos deben ir a logging/observabilidad apropiados, no contaminar la historia administrativa. `before`/`after` de cambios de dominio deben ser arrays minimizados; el helper aplica `AuditSanitizer` antes de persistirlos. Para distinguir un no-op de un fallo del logger antes de escribir, el proyecto puede llamar `AuditLogger::prepareForRecord()`.

## Datos sensibles

Nunca registrar contraseñas, hashes, tokens, cookies, secretos, claves API, CVV ni números completos de tarjeta. `AuditSanitizer` ofrece una protección base, pero cada proyecto debe revisar campos específicos de su dominio antes de almacenar snapshots.

Guardar solo los campos necesarios. En muchos eventos basta con IDs, acción y metadatos mínimos.

## Evidencia histórica e inmutabilidad lógica

Un registro puede cambiar de estado sin dejar de ser evidencia histórica. Si una entidad participó en un cierre, factura, corte, conciliación, liquidación o snapshot congelado, una mutación posterior no debe destruir la información mínima necesaria para reconstruir o justificar aquel resultado.

Ejemplos genéricos:

- un pago invalidado después de un cierre puede seguir siendo evidencia de lo que estaba vigente cuando el cierre se generó;
- una corrección posterior no debe borrar la relación que explica un total histórico congelado;
- una eliminación definitiva debe comprobar referencias históricas antes de borrar registros de soporte.

Cuando el orden de dos eventos no pueda determinarse por la precisión temporal disponible, preservar la trazabilidad es preferible a asumir que la evidencia puede eliminarse.

## Ejemplo

```php
$logger->record([
    'event_kind' => AuditLogger::DOMAIN_CHANGE,
    'actor_type' => 'user',
    'actor_id' => (string) $user['id'],
    'actor_role' => $user['role'],
    'site_id' => (string) $siteId,
    'action' => 'payment.invalidated',
    'entity_type' => 'payment',
    'entity_id' => (string) $paymentId,
    'source' => 'admin',
    'before' => AuditSanitizer::sanitize($before),
    'after' => AuditSanitizer::sanitize($after),
]);
```

Un resultado técnico separado no debe compartir snapshots con la mutación:

```php
$logger->record([
    'event_kind' => AuditLogger::TECHNICAL_RESULT,
    'action' => 'request.completed',
    'entity_type' => 'request',
    'request_id' => $requestId,
]);
```

## Automatizaciones

Una acción de n8n u otro proceso puede usar `actor_type=automation` y un `actor_id` estable como `n8n.billing-reminder`. No fingir que una automatización fue un usuario humano.

## Fallos de auditoría

El helper devuelve `false` si no puede registrar. Cada proyecto debe decidir qué operaciones son **fail closed** (la mutación se cancela si no puede auditarse) y cuáles pueden continuar registrando el fallo por otro canal. Para operaciones financieras o de permisos, considerar una política más estricta.

## Retención

Definir por proyecto. Vigilar crecimiento de `audit_events`, establecer un periodo compatible con necesidades operativas/legales y archivar o purgar de forma controlada. No eliminar eventos simplemente para reducir tamaño sin una política documentada.
