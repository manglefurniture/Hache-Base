# Observability — P2-01 / P2-02

Extension **opt-in** para conectar logs, métricas y trazas a una plataforma de observabilidad sin acoplar Hache Base a un proveedor, y para definir alertas accionables/runbooks sin imponer thresholds universales.

## P2-01 — observabilidad neutral

Este paquete implementa la frontera reusable de P2-01:

- `TelemetryExporter.php` — único punto que puede hablar con OpenTelemetry/APM/stdout/archivo u otro sink del proyecto;
- `TraceContext.php` — generación y propagación estricta de `traceparent` W3C v00, con rechazo de IDs inválidos o all-zero;
- `ObservabilityBridge.php` — envelope neutral para eventos, counters, histogramas y spans medidos;
- reutiliza `RequestContext` para `request_id`/`correlation_id` y `StructuredLogger::redact()` como primera capa de minimización.

No instala SDK, collector, agent, sidecar, SaaS, endpoint remoto ni dependencia Composer. Tampoco activa telemetría en Core ni en proyectos derivados.

## Contrato de datos

Todos los records exportados incluyen:

- `schema_version`;
- `kind` (`log`, `metric` o `span`);
- UTC timestamp;
- `service`, `environment`, `version`, `name`;
- `request_id`, `correlation_id`;
- `trace_id`, `span_id`, `parent_span_id`, `sampled`;
- `attributes` minimizados.

Los metrics añaden `metric_type` y `value`; histogram añade `unit`. Los spans añaden `started_at`, `ended_at`, `duration_ms` y `status`.

## Contexto por request/job

`request_id` y `correlation_id` son datos de una **frontera de ejecución concreta**. La Extension no mantiene un contexto implícito permanente dentro de `ObservabilityBridge`, porque una misma instancia puede vivir más que un request en workers persistentes.

El proyecto debe elegir una de estas dos formas:

1. pasar el mismo `RequestContext` explícitamente a cada `event()`, `counter()`, `histogram()` o `measure()` de ese request/job; o
2. inyectar un `boundaryContext` al construir un bridge que esté scoped únicamente a ese request/job.

Si no se pasa un contexto explícito ni se inyecta uno de frontera, la operación falla antes de exportar. En RoadRunner, Swoole, workers de cola o cualquier runtime persistente, nunca reutilizar entre requests/jobs un bridge que tenga `boundaryContext` de una ejecución anterior.

## Privacidad y cardinalidad

La Extension no autoriza enviar datos personales. `attributes` pasa por la redacción de `StructuredLogger` y además bloquea claves de alta probabilidad de PII como email, teléfono, dirección, IDs de usuario/cliente/alumno, IP, user-agent, referrer, session ID, query string y URL completa.

Eso es una defensa adicional, **no** una garantía de anonimización. El proyecto debe usar atributos de baja cardinalidad como:

- nombre de CUF/operación;
- plantilla de ruta, nunca URL cruda;
- método HTTP;
- clase de status;
- proveedor/adaptador;
- estado interno no sensible;
- resultado agregado.

No incluir payloads, bodies, mensajes de excepción, emails, teléfonos, nombres, tokens ni IDs de negocio.

## Trazas

`TraceContext::fromTraceparent()` acepta solamente formato v00 lowercase válido. El contexto recibido representa el parent remoto; `ObservabilityBridge::measure()` crea un span hijo local y entrega su `TraceContext` al callback para propagar `traceparent()` downstream.

No se implementa `tracestate`/baggage en Base. Si un proveedor lo requiere, debe quedar detrás de su exporter/adaptador y documentarse en el proyecto.

## Fallos del exporter

La exportación es **fail-open por default**: un fallo del backend APM no debe tumbar el CUF. Puede configurarse `onExportFailure` para dejar señal local y `failOpen=false` solamente cuando un entorno de prueba quiera convertir la exportación en gate.

Si la operación instrumentada falla, `measure()` emite solo `exception_type`; nunca copia el mensaje de excepción al record, y siempre vuelve a lanzar la excepción original aunque falle la telemetría.

## P2-02 — alertas y runbooks

P2-02 permanece vendor-neutral. Hache Base no crea monitores reales ni routing; entrega un contrato project-owned:

- `templates/ALERTING-RUNBOOKS.md` — golden signals/CUF, thresholds, ventanas, severidad, routing, control de ruido y runbook mínimo;
- `templates/alert-policy.example.json` — ejemplo ficticio machine-readable;
- `tools/observability/validate-alert-policy.mjs` — checker sin dependencias externas.

Signals permitidas:

- `latency`, `traffic`, `errors`, `saturation`;
- `cuf_success`, `cuf_failure`, `cuf_pending`.

Cada alerta debe tener threshold, ventana, tiempo sostenido, owner, acción y runbook. El checker valida que esos campos existan y sean coherentes; **no** decide si el threshold es correcto ni si una alerta es útil en producción.

Ejemplo de validación:

```bash
node tools/observability/validate-alert-policy.mjs alert-policy.json
```

## Adopción por proyecto

Antes de activar P2-01 completar `templates/OBSERVABILITY-ADOPTION.md` y definir:

1. CUF y señales que justifican observabilidad;
2. exporter/backend elegido y owner;
3. sampling, retención y coste;
4. atributos permitidos y control de cardinalidad;
5. endpoint/auth/egress fuera del código;
6. qué ocurre si el exporter falla;
7. evidencia de request → job/webhook/proveedor cuando aplique;
8. procedimiento de desactivación sin romper el producto.

Antes de activar P2-02 completar `templates/ALERTING-RUNBOOKS.md`, versionar la política de alertas y probar al menos una condición positiva y una negativa/control de ruido en un entorno apropiado.

## Límite de evidencia

Que este paquete exista o sus tests pasen no convierte `OBS-*` ni ningún proyecto en PASS. La evidencia normativa sigue perteneciendo al proyecto y a su entorno real.
