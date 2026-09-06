# Alerting + Runbooks — plantilla P2-02

> Plantilla de adopción por proyecto para alertas accionables sobre golden signals y Critical User Flows. No define umbrales universales y no convierte controles `OBS-*` en PASS.

## 1. Proyecto y owner

- Proyecto:
- Nivel A/B/C:
- Owner de operación:
- Fecha de revisión:
- Backend/monitor que evalúa las señales:
- Ruta del archivo `alert-policy.json` versionado:

## 2. Principio

Una alerta existe para provocar una acción concreta. No crear alertas solo porque una métrica existe.

Para cada CUF/integración relevante considerar, según aplique:

- **latency** — cuánto tarda el resultado que importa;
- **traffic** — volumen/tasa de uso;
- **errors** — errores técnicos o dependencia no disponible;
- **saturation** — recurso acercándose a su capacidad;
- **cuf_success** — resultado autoritativo exitoso;
- **cuf_failure** — fallo final/accionable;
- **cuf_pending** — operaciones aceptadas/ambiguas que no llegan a resolución.

No todas las señales requieren alerta. Si no existe una acción útil ante el umbral, documentar la métrica para observación y no paginar/avisar por ruido.

## 3. Matriz de alertas

| ID | CUF / integración | Señal | Métrica | Condición | Ventana | Persistencia | Severidad | Owner | Acción inmediata | Runbook |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  |  | latency / traffic / errors / saturation / cuf_success / cuf_failure / cuf_pending |  |  |  |  |  |  |  |  |

Cada fila debe corresponder a una entrada de `alert-policy.json` validable con:

```bash
node tools/observability/validate-alert-policy.mjs alert-policy.json
```

El checker exige ID, CUF, signal, métrica, operador, threshold, ventana, tiempo sostenido, severidad, owner, runbook, acción y data source. No decide si el threshold de negocio es correcto.

## 4. Cómo fijar un threshold

Para cada alerta documentar:

- baseline/evidencia usada:
- por qué ese threshold importa al usuario/negocio:
- por qué la ventana elegida reduce ruido sin esconder una incidencia:
- quién aprobó el threshold:
- fecha de próxima revisión:

Evitar límites copiados de otro proyecto. Un p95/p99, ratio o backlog solo es útil si su definición y fuente están estables.

## 5. Severidad y routing

Definir significado local, sin asumir un proveedor:

- `info` — señal que merece revisión pero no interrupción inmediata;
- `warning` — degradación accionable dentro del horario/ventana definida;
- `critical` — CUF crítico comprometido o riesgo que exige acción inmediata.

Routing real:

- canal/sistema:
- horario/on-call:
- fallback si el canal falla:
- dedupe/silence durante incidente conocido:
- owner que puede cerrar o ajustar la alerta:

## 6. Runbook mínimo por alerta

Cada `runbook` debe contener:

1. **Qué significa** la alerta y qué no demuestra.
2. **Cómo confirmar** que el síntoma es real usando una segunda señal o evidencia autoritativa cuando aplique.
3. **Primeras acciones seguras** y qué acciones están prohibidas (por ejemplo retry ciego de una operación ambigua).
4. **Cómo localizar** request/correlation/trace IDs sin buscar PII.
5. **Dependencias** que revisar y fallback conocido.
6. **Recovery**: rollback, reconciliación, failover manual u otro procedimiento que ya esté aprobado.
7. **Escalación** y owner.
8. **Criterio de cierre** de incidente y verificación posterior.
9. **Qué evidencia conservar** para post-incident/revisión.

## 7. Control de ruido

Antes de activar una alerta:

- probar que una condición sana no dispara repetidamente;
- probar una condición fixture/staging que sí deba disparar;
- comprobar que `for_seconds`/ventana no ocultan un fallo crítico ni reaccionan a un pico irrelevante;
- definir dedupe/silence del backend, si existe;
- revisar cardinalidad de labels/attributes;
- confirmar que el aviso contiene suficiente contexto para iniciar el runbook, sin secretos ni PII.

## 8. Evidencia

- archivo `alert-policy.json` validado:
- captura/export de configuración real del monitor:
- prueba positiva de disparo:
- prueba negativa/ruido:
- evidencia de routing:
- runbooks revisados:
- revisión humana / fecha:

## 9. Estado

- `NOT EVALUATED` / `PARTIAL` / `PASS` / `N/A`:
- justificación:
- enlaces de evidencia:

P2-02 en Hache Base entrega contrato y guardrails; el proyecto debe demostrar que sus alertas reales tienen threshold, ventana, owner y runbook y que conducen a una acción útil.
