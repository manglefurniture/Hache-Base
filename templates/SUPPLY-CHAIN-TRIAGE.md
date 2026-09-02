# SUPPLY CHAIN — TRIAGE Y EVIDENCIA

> Copiar por proyecto cuando P0-12 aplique. Esta plantilla no convierte findings en PASS por sí sola.

## Perfil

- Proyecto:
- Nivel A/B/C:
- Owner técnico:
- Owner de seguridad/riesgo:
- Fecha de revisión:
- `SUPPLY_CHAIN_MODE`: report / baseline / block
- `SUPPLY_CHAIN_STACK_ROOTS`:

## Stacks y lockfiles

| Stack/root | Manifest | Lockfile | SCA tool/evidencia | Licencias inventariadas | Estado |
| --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |

## Secret scan

- Alcance ejecutado (árbol actual/history/tool externo):
- Commit exacto:
- Reporte/evidencia:
- Findings reales:
- Revocación/rotación requerida:
- Confirmación de remoción:

Un secreto real no se acepta mediante `accepted-risk.json`.

## Vulnerabilidades / SEC-014

| Finding ID | Paquete/advisory | Severidad | Alcanzabilidad/contexto | Decisión | Mitigación/aislamiento | Owner | Aprobación | Expira | Evidencia |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |  |  |  |  |

Decisiones permitidas para critical/high B/C antes de release:

- actualizar/remover dependencia;
- demostrar que no es explotable en el contexto real;
- aplicar mitigación/aislamiento equivalente documentado y aprobado;
- detener release.

## SLA

Baseline Hache Base desde primera detección real:

- critical: 24 h;
- high: 72 h;
- medium: 14 días;
- low: 30 días.

Registrar aquí la fecha de primera detección y la fecha límite; CI no la inventa.

## Licencias

- Política/denylist aprobada por:
- Fecha:
- Dependencias con metadata ausente:
- Excepciones/revisión legal:
- Evidencia:

Hache Base no define una denylist legal universal.

## Cierre

- [ ] Lockfiles presentes para cada stack declarado.
- [ ] Secret scan ejecutado y findings reales revocados/rotados.
- [ ] SCA no está `NOT EVALUATED` para stacks que requieren SEC-014.
- [ ] Critical/high B/C resueltos o mitigados/aprobados con expiración.
- [ ] Licencias revisadas según política del proyecto.
- [ ] CI ejecutó el modo acordado sobre el commit exacto.
- [ ] Evidencia adjunta al release/auditoría.
