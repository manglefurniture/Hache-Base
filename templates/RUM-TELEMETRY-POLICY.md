# RUM / Web Vitals — Telemetry Policy Template

> Completar por proyecto antes de activar `integrations/rum/` en producción. Esta plantilla no define una base legal universal ni sustituye revisión de privacidad.

## 1. Propósito y responsable

- Proyecto:
- Owner técnico:
- Owner de privacidad/negocio:
- Propósito concreto de RUM:
- CUF/plantillas cubiertos:
- Entorno(s):

## 2. Decisión de activación

- Estado: `DISABLED` / `PILOT` / `ENABLED`
- Jurisdicción(es) aplicable(s):
- Decisión sobre consentimiento/base aplicable:
- Responsable que aprobó la decisión:
- Fecha de revisión:
- Próxima revisión:

Hache Base exige una decisión explícita del proyecto; no presupone que analytics/RUM pueda activarse sin consentimiento ni que siempre lo requiera.

## 3. Datos permitidos

| Campo | Uso | Cardinalidad esperada | ¿Puede identificar persona? |
| --- | --- | --- | --- |
| `metric` | LCP/INP/CLS | 3 | No |
| `value` | Medición técnica | numérica | No por sí sola |
| `route_group` | CUF/plantilla abstracta | baja | No; nunca URL/path |
| `build_id` | Release/artefacto | baja | No |
| `form_factor` | mobile/desktop | 2 | No |

Campos prohibidos por defecto: URL/path/query exactos, referrer, cookies, session/account ID, email, teléfono, nombre, User-Agent completo, IP persistida, fingerprint y cualquier payload de negocio.

## 4. Transporte y collector

- Endpoint same-origin:
- Máximo de body:
- Rate limit:
- ¿Rechaza campos desconocidos?:
- ¿El access/app log excluye el body?:
- ¿Usa autenticación/cookies?: `NO` esperado
- Controles contra abuso:

## 5. Sampling y cobertura

- `sampleRate`:
- Regla de selección:
- Breakpoint/regla `mobile` vs `desktop`:
- Route groups versionados:
- Builds incluidos:
- Fecha/hora inicio de ventana:
- Fecha/hora fin de ventana:
- Mínimo de muestras que el proyecto considera suficiente:
- Justificación del mínimo:
- Riesgos de sesgo conocidos:

No usar identificador persistente para estabilizar sampling entre sesiones salvo que exista revisión específica de privacidad.

## 6. Retención y acceso

- Retención máxima de eventos crudos:
- Retención de agregados:
- Frecuencia de agregación:
- Roles con acceso a crudos:
- Roles con acceso a agregados:
- Procedimiento de borrado:
- Backups que pueden contener crudos y expiración:

## 7. Terceros

- SDK/proveedor usado para obtener Web Vitals:
- Collector/analytics externo, si existe:
- Datos compartidos:
- Región de tratamiento:
- DPA/contrato/revisión aplicable:
- Procedimiento de desactivación:

Si se adopta un tercero, actualizar el inventario de terceros/privacidad correspondiente; Hache Base no lo declara seguro por existir este patrón.

## 8. Evidencia PERF-001

Adjuntar por cada ventana evaluada:

- reporte p75;
- commit/build;
- CUF/route groups;
- cobertura móvil y desktop;
- sample counts;
- incidentes/cambios durante la ventana;
- decisión humana sobre suficiencia;
- resultado de revisión.

Un grupo `within_target: true` o `meets_project_sample_floor: true` es evidencia parcial, no un `PASS` automático de `PERF-001`.

## 9. Rollback / kill switch

- Cómo desactivar RUM sin deploy:
- Cómo desactivar RUM con deploy:
- Responsable:
- Tiempo objetivo:
- Verificación de que dejaron de llegar eventos:
