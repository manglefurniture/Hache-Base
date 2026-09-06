# Observability — P2-01

Extension **opt-in** para conectar logs, métricas y trazas a una plataforma de observabilidad sin acoplar Hache Base a un proveedor.

## Alcance

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

## Fallos

La exportación es **fail-open por default**: un fallo del backend APM no debe tumbar el CUF. Puede configurarse `onExportFailure` para dejar señal local y `failOpen=false` solamente cuando un entorno de prueba quiera convertir la exportación en gate.

Si la operación instrumentada falla, `measure()` emite solo `exception_type`; nunca copia el mensaje de excepción al record, y siempre vuelve a lanzar la excepción original aunque falle la telemetría.

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

## Límite de evidencia

Que este paquete exista o sus tests pasen no convierte `OBS-*` ni ningún proyecto en PASS. La evidencia normativa sigue perteneciendo al proyecto y a su entorno real.
