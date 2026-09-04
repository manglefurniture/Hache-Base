# Collector contract — Web Vitals / RUM

Este contrato define el mínimo de servidor para adoptar `integrations/rum/` sin convertir una muestra de performance en un registro de navegación personal.

## Entrada

- método `POST`;
- endpoint same-origin dedicado;
- `Content-Type: application/json`;
- body pequeño; recomendación de referencia: máximo 1024 bytes;
- esquema exacto `schema_version = 1`;
- campos permitidos únicamente:
  - `metric`: `LCP`, `INP` o `CLS`;
  - `value`: número finito no negativo;
  - `route_group`: etiqueta deliberada de baja cardinalidad;
  - `build_id`: identificador de artefacto/release;
  - `form_factor`: `mobile` o `desktop`.

Rechazar campos desconocidos en lugar de almacenarlos.

## Minimización en servidor

Aunque el navegador ya minimiza, el collector debe repetir la validación y **no** enriquecer cada evento con:

- URL/path/query exactos;
- referrer;
- cookies o session/account IDs;
- email, teléfono, nombre u otro dato de negocio;
- User-Agent completo;
- IP cruda o hash persistente;
- fingerprint o identificador estable.

El servidor inevitablemente recibe metadatos de red durante la solicitud. Pueden usarse de forma transitoria para controles técnicos como rate limiting, pero el patrón de Hache Base no los incorpora al evento RUM ni los conserva como identificador de analítica.

## Autenticación y cookies

El endpoint está pensado para telemetría anónima/minimizada y el cliente usa `credentials: "omit"`. No debe requerir sesión autenticada ni aprovechar cookies existentes para correlacionar métricas con personas.

Si un proyecto decide lo contrario por un requisito real, deja de cumplir este contrato y necesita threat/privacy review específica.

## Logging

- no registrar el body completo en access/application logs;
- no imprimir payloads inválidos;
- registrar solo contadores/códigos de rechazo de baja cardinalidad;
- aplicar límites de tamaño y rate limit antes de parsear o persistir cuando la infraestructura lo permita.

## Retención y agregación

El proyecto define y documenta:

- ventana de medición;
- sampling;
- retención máxima de eventos crudos;
- acceso a datos crudos;
- frecuencia de agregación;
- retención de agregados;
- mecanismo de borrado;
- mínimo de muestras considerado suficiente para su contexto.

La recomendación operativa es conservar crudos solo el tiempo necesario para agregación/diagnóstico y trabajar después con p75 por `route_group`, `build_id`, `form_factor` y métrica.

Hache Base no fija un número universal de días ni de muestras.

## Estado de Production Readiness

El collector y el resumen p75 generan evidencia. No deben escribir `PASS` en `PERF-001` automáticamente.

La persona revisora del proyecto debe verificar:

- ventana y volumen suficientes;
- cobertura de CUF/plantillas;
- móvil y desktop;
- representatividad del tráfico;
- thresholds;
- política de privacidad/consentimiento aplicable;
- incidentes o sesgos conocidos de sampling.

Solo después puede adjuntarse la evidencia al proceso de Production Readiness.
