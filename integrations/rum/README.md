# Web Vitals / RUM opt-in

P1-04 aporta un patrón reutilizable de Real User Monitoring para `LCP`, `INP` y `CLS` sin introducir telemetría en el Core ni imponer proveedor, SDK, consentimiento o base legal universal.

La extensión está **apagada por defecto**: `createRumReporter()` solo envía cuando la función `shouldCollect()` del proyecto devuelve exactamente `true`.

## Objetivos

- producir evidencia de campo útil para `PERF-001` por CUF/plantilla, build y clase `mobile`/`desktop`;
- minimizar datos antes de salir del navegador;
- no crear identificadores persistentes ni correlacionar sesiones;
- mantener el transporte same-origin y sin credenciales;
- conservar la decisión de consentimiento/ley en el proyecto;
- permitir agregación p75 reproducible sin convertirla automáticamente en `PASS`.

## Payload permitido

El cliente solo emite:

```json
{
  "schema_version": 1,
  "metric": "LCP",
  "value": 1834,
  "route_group": "registration",
  "build_id": "20260904.1",
  "form_factor": "mobile"
}
```

`route_group` debe ser una etiqueta deliberada de baja cardinalidad (`home`, `registration`, `checkout`) y **no** una URL, pathname, query, slug de usuario o contenido libre. `build_id` debe identificar el artefacto/release sin identificar personas.

No se aceptan campos adicionales. En particular, la extensión no envía URL exacta, query, referrer, User-Agent, IP, cookie, session ID, email, teléfono, nombre, account ID, fingerprint ni el `id` interno que puedan producir algunas librerías de Web Vitals.

## Integración del cliente

Hache Base no agrega `web-vitals` ni otro SDK a dependencias del Core. El proyecto puede inyectar un proveedor que exponga `onLCP`, `onINP` y `onCLS`:

```js
import {onCLS, onINP, onLCP} from 'web-vitals';
import {
  coarseFormFactor,
  createRumReporter,
  wireWebVitals,
} from './integrations/rum/web-vitals-rum.mjs';

const reporter = createRumReporter({
  endpoint: '/__rum/web-vitals',
  routeGroup: 'registration',
  buildId: window.APP_BUILD_ID,
  formFactor: () => coarseFormFactor(window.innerWidth, 768),
  sampleRate: 0.1,
  shouldCollect: () => telemetryPolicyAllowsRum() === true,
});

wireWebVitals({onLCP, onINP, onCLS}, reporter);
```

El callback de política puede representar consentimiento, interés legítimo u otra decisión aplicable al proyecto. Hache Base no decide cuál corresponde.

## Transporte y fallos

El transporte por defecto usa `fetch` con:

- ruta same-origin sin query/fragment;
- `credentials: "omit"`;
- `referrerPolicy: "no-referrer"`;
- `cache: "no-store"`;
- `redirect: "error"`;
- `keepalive: true`.

No se usa `sendBeacon` porque no permite expresar de forma equivalente la política `credentials: "omit"`.

La telemetría nunca debe romper el CUF: errores de policy callback, sampler, normalización o red se convierten en estado de descarte y no se propagan a la aplicación.

## Contrato del collector

Ver `COLLECTOR-CONTRACT.md`. El servidor debe aplicar minimización otra vez, rechazar campos desconocidos, evitar loguear el body y no persistir IP/User-Agent como parte del evento RUM.

El proyecto debe completar `templates/RUM-TELEMETRY-POLICY.md` antes de activar esta extensión en producción.

## Evidencia p75

`field-p75.mjs` agrega muestras minimizadas por:

- métrica;
- `route_group`;
- `build_id`;
- `form_factor`.

Usa percentil p75 por método `nearest-rank` y compara con los límites normativos de `PERF-001`:

- LCP ≤ 2500 ms;
- INP ≤ 200 ms;
- CLS ≤ 0.1.

No existe un mínimo universal de muestras en Core. `minimumSampleCount` es una decisión explícita del proyecto y puede dejarse en `null`; aun cuando se configure y todos los grupos estén dentro del target, el resumen conserva `production_readiness_state: "NOT EVALUATED"` y `decision: "HUMAN_REVIEW_REQUIRED"`.

## Límites

P1-04 no demuestra por sí solo que exista tráfico suficiente, una ventana representativa, cobertura de todos los CUF, móvil y desktop, ni cumplimiento legal. Tampoco sustituye Lighthouse de laboratorio, revisión humana de accesibilidad, política de privacidad ni inventario de terceros.

Es una Extension opt-in para producir evidencia minimizada; la evaluación final permanece en el proyecto.
