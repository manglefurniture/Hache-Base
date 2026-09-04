# P1-01 — Production Readiness CI report

Este documento describe el **reporte derivado** implementado por `tools/production-readiness/report.php`.

No es una segunda norma. La única fuente normativa sigue siendo `PRODUCTION-READINESS-STANDARD.md`, en especial el registro canónico de la sección 24.

## Objetivo

Generar una proyección auditable por nivel A/B/C que permita a CI, una persona o una revisión automática ver los mismos IDs y metadatos canónicos sin copiar ni reinterpretar la Checklist.

El reporte:

- lee directamente las 126 filas del registro canónico del Standard;
- resuelve qué controles entran por nivel A/B/C;
- conserva condiciones de aplicabilidad, severidad canónica, evidencia mínima, automatización y revisión humana;
- calcula la severidad efectiva para el nivel seleccionado;
- inicializa todo control aplicable como `NOT EVALUATED` si no existe evidencia explícita;
- nunca convierte ausencia de evidencia en `PASS`;
- no declara por sí solo que un proyecto está Production Ready.

Los controles cuyo nivel mínimo es superior al nivel seleccionado se marcan como `scope=out_of_level`. Esto **no** equivale a `N/A`: simplemente no forman parte de la proyección de ese nivel.

Los controles con una condición adicional, por ejemplo «cuando hay sesiones», siguen dentro del nivel y permanecen `NOT EVALUATED` hasta que el proyecto demuestre `PASS`, `FAIL` o un `N/A` justificado.

## Uso

Generar JSON por nivel:

```bash
php tools/production-readiness/report.php --level A --json /tmp/readiness-a.json
php tools/production-readiness/report.php --level B --json /tmp/readiness-b.json
php tools/production-readiness/report.php --level C --json /tmp/readiness-c.json
```

Generar JSON y Markdown:

```bash
php tools/production-readiness/report.php \
  --level B \
  --json /tmp/readiness-b.json \
  --markdown /tmp/readiness-b.md
```

Sin `--json` ni `--markdown`, el JSON se escribe a stdout.

## Evidencia explícita opcional

`--evidence` acepta un JSON con metadata del proyecto y estados por ID:

```json
{
  "project": {
    "name": "mi-proyecto",
    "environment": "staging",
    "commit": "abc123"
  },
  "controls": {
    "GOV-001": {
      "state": "PASS",
      "evidence": ["docs/project-profile.md"],
      "reviewed_by": "persona-revisora",
      "reviewed_at": "2026-09-04"
    },
    "PERF-001": {
      "state": "N/A",
      "justification": "Todavía no existe tráfico de campo suficiente; se evalúa PERF-002.",
      "evidence": ["reports/lab-baseline.md"],
      "reviewed_by": "persona-revisora",
      "reviewed_at": "2026-09-04"
    }
  }
}
```

Estados permitidos: `PASS`, `FAIL`, `N/A`, `NOT EVALUATED`.

Guardrails:

- `PASS` exige al menos una referencia de evidencia;
- `FAIL` exige evidencia o una nota;
- `N/A` exige justificación y evidencia;
- si el registro canónico marca `Humana=Sí`, `PASS` y `N/A` exigen `reviewed_by` y `reviewed_at` con fecha calendario `YYYY-MM-DD`;
- IDs desconocidos o metadata inválida terminan con exit code `2`;
- el reporte conserva el SHA-256 del Standard usado para hacerlo trazable.

El campo `reviewed_by` registra una afirmación aportada por el proyecto; el script no verifica identidad ni reemplaza aprobación humana real.

## Semántica CI

P1-01 es **reporting**, no un nuevo gate universal. El reporte expone `blocking_or_required_unresolved` y `human_review_pending`, pero mantiene `decision=NOT_A_PRODUCTION_READY_DECLARATION`.

La decisión final sigue perteneciendo al Standard, la Checklist y la evidencia real del proyecto. Un pipeline verde solo demuestra que el reporte pudo generarse y que sus regresiones pasaron; no demuestra que el proyecto está Production Ready.
