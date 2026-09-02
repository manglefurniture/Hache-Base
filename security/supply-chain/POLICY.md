# P0-12 — Supply-chain policy

Este paquete implementa el baseline reusable de P0-12 sin convertir Hache Base en un proveedor de SCA ni imponer decisiones legales universales.

## Alcance

P0-12 cubre:

- guardrail de lockfiles para stacks declarados;
- secret scan de firmas de alta confianza sobre archivos de texto actualmente trackeados;
- SCA para Composer y npm cuando existe lockfile compatible y hay herramienta/evidencia disponible;
- inventario de licencias desde lockfiles compatibles;
- modos `report`, `baseline` y `block`;
- registro explícito de mitigaciones/riesgo aceptado para findings SCA con owner, aprobación y expiración;
- SLA de triage versionado.

No cubre SBOM/provenance, pinning de GitHub Actions/containers por digest ni scans históricos exhaustivos; eso pertenece a madurez posterior/P2-06 o a tooling específico del proyecto.

## Relación normativa

- **SEC-013**: los secretos no pueden quedar versionados ni expuestos. El scanner de P0-12 busca únicamente patrones de alta confianza y nunca imprime el valor detectado. Un hit real no se “acepta”: se revoca/rota y se elimina del árbol/historia según corresponda.
- **SEC-014**: en niveles B/C una vulnerabilidad crítica/alta explotable no se libera sin actualización, mitigación equivalente o aislamiento documentado y aprobado. El gate puede bloquear findings reales `critical/high` en `block`; en A se reportan y requieren triage, sin elevar automáticamente la severidad normativa.

La mera existencia de `check.php` o un reporte sin blockers **no demuestra** que SEC-013/SEC-014 estén PASS en un proyecto si el alcance de scan/SCA no cubre su stack real. El reporte expone `not_evaluated` y `evidence_complete` para impedir confundir ausencia de evidencia con PASS.

## Modos

### `report`

Genera evidencia y deja los findings como no bloqueantes. Se usa para primera adopción y baseline.

### `baseline`

Bloquea solo las categorías de baja ambigüedad configuradas en `policy.json`: por default `secret` y `lockfile`. SCA y licencias se registran sin bloquear para permitir triage inicial.

### `block`

Aplica la política de findings evaluados:

- secretos y manifests sin lockfile bloquean;
- findings SCA reales `critical/high` bloquean en B/C salvo mitigación aprobada vigente;
- `sca_unavailable` permanece **NOT EVALUATED**, no se convierte artificialmente en vulnerabilidad ni blocker SEC-014;
- licencias solo bloquean según `license-policy.json` del proyecto.

Un exit code 0 con `not_evaluated > 0` no significa Production Ready: el proyecto todavía necesita completar la evidencia antes del release según el Standard/checklist aplicable.

## Stacks y lockfiles

`SUPPLY_CHAIN_STACK_ROOTS` acepta raíces relativas separadas por coma, por ejemplo:

```bash
SUPPLY_CHAIN_STACK_ROOTS=".,frontend" php security/supply-chain/check.php
```

Cada raíz puede declarar Composer (`composer.json` + `composer.lock`) o Node (`package.json` + lockfile). El inventario de manifests y lockfiles se atribuye al **árbol de `HEAD`**, no al índice ni a archivos generados localmente. Un lockfile creado o añadido con `git add` pero todavía ausente del commit revisado no constituye evidencia reproducible de ese SHA y se trata como lock no comprometido/NOT EVALUATED para SCA y licencias.

En Node, si `package.json` declara `packageManager`, el lockfile debe corresponder a ese manager:

- `npm` → `package-lock.json` o `npm-shrinkwrap.json`;
- `yarn` → `yarn.lock`;
- `pnpm` → `pnpm-lock.yaml`.

Combinaciones ambiguas con más de un lockfile en `HEAD` se rechazan. Si `packageManager` no existe, se admite exactamente uno de los lockfiles reconocidos; el proyecto sigue siendo responsable de fijar su toolchain de forma reproducible.

Para npm, el lock soportado debe tener `lockfileVersion` 2/3, una entrada raíz válida y conjuntos de dependencias coherentes con `package.json`. Además, cada dependencia directa o transitiva declarada por un paquete debe resolverse desde ubicaciones alcanzables por la resolución jerárquica de Node; una copia anidada bajo un paquete hermano no satisface el requisito. Un grafo truncado queda inválido.

Para Composer, `composer.lock` debe contener `packages`/`packages-dev` válidos, cubrir los requisitos directos no-plataforma de `composer.json` y mantener cerrado el grafo transitivo declarado por los `require` de los paquetes bloqueados. Las versiones bloqueadas deben satisfacer las restricciones Composer que el checker puede evaluar; si una restricción no puede evaluarse de forma confiable, el lock no se eleva a evidencia completa.

Un lock ausente, no comprometido, inválido, truncado o desalineado deja SCA y licencias explícitamente **NOT EVALUATED**; no puede producir `evidence_complete=true`.

El parser SCA/licencias integrado cubre `composer.lock`, `package-lock.json` y `npm-shrinkwrap.json`. `pnpm-lock.yaml`/`yarn.lock` cuentan como lockfiles de reproducibilidad, pero SCA y licencias quedan explícitamente `NOT EVALUATED` hasta aportar evidencia específica del proyecto.

## SCA

Para ejecución real:

- Composer: `composer audit --locked --format=json --no-interaction`;
- npm: `npm audit --package-lock-only --json`.

Si la herramienta no existe, falla la red, el JSON no es interpretable o el lockfile no tiene parser integrado, el resultado es `sca_unavailable`: **NOT EVALUATED**. Ese estado no es PASS ni una vulnerabilidad demostrada y por eso no se eleva artificialmente a blocker SEC-014.

Las variables `SUPPLY_CHAIN_COMPOSER_AUDIT_FILE` y `SUPPLY_CHAIN_NPM_AUDIT_FILE` existen para fixtures/evidencia pre-generada; no son un bypass de producción. Un único archivo pre-generado solo se acepta cuando la invocación contiene exactamente un stack del mismo ecosistema. Si `SUPPLY_CHAIN_STACK_ROOTS` contiene varios stacks Composer o varios stacks Node, la evidencia pre-generada única se considera de alcance ambiguo y esos stacks quedan `NOT EVALUATED`; se debe dividir la ejecución o generar/auditar evidencia por stack.

## Secret scan

El baseline analiza línea por línea los archivos de texto pertenecientes al árbol trackeado de `HEAD`, sin omitir silenciosamente archivos grandes, mediante firmas de alta confianza: private keys, AWS access keys, tokens GitHub clásicos y fine-grained (`github_pat_...`), Slack tokens, OpenAI keys, Stripe live secrets y Google API keys.

Los archivos binarios se contabilizan aparte (`binary_skipped`) y el alcance declarado es `tracked_text_tree`; no se afirma que contenido binario sea evaluado como texto. Si un archivo de texto regular no puede leerse, `secret_scan` conserva evidencia incompleta/NOT EVALUATED aunque posteriormente encuentre otros secretos.

Los symlinks trackeados **no se dereferencian**. Se analiza el contenido del blob del enlace almacenado en `HEAD` (la ruta objetivo versionada), nunca el contenido del archivo externo al que apunte el working tree. El reporte contabiliza esos enlaces mediante `symlink_blobs_scanned`.

El reporte conserva solo `rule`, archivo y línea. Nunca persiste el valor detectado.

`secret-scan.allowlist` solo puede usarse para fixtures falsos deliberados. Cada entrada debe ser una **ruta exacta** bajo `tests/` o `fixtures/` y una regla exacta reconocida; no se permiten globs, `*` ni rutas de runtime como `src/`.

Formato:

```text
tests/fixtures/fake-secret.txt openai_key
```

Un secreto real requiere revocación/rotación y remoción; `accepted-risk.json` nunca se aplica a findings `secret`.

El scan actual no equivale a un scan exhaustivo del historial Git. Si un proyecto pudo haber versionado secretos previamente, debe añadir evidencia de history scan/rotación con tooling especializado.

## Riesgo aceptado / mitigación SEC-014

`accepted-risk.json` admite excepciones únicamente para findings SCA `vulnerability` por `finding_id`. Para ser vigentes deben contener:

- `owner`;
- `approval_ref`;
- `mitigation`;
- `expires_at` en formato canónico `YYYY-MM-DD` y no expirado.

Una excepción incompleta, mal formada o expirada no desactiva el bloqueo. Este mecanismo representa mitigación/aislamiento aprobado de SEC-014; no autoriza secretos ni findings de lockfile/licencias.

Ejemplo:

```json
{
  "finding_id": "<id-del-reporte>",
  "owner": "security-owner",
  "approval_ref": "INC-123/PR-456",
  "mitigation": "feature disabled and dependency unreachable from production CUF",
  "expires_at": "2026-09-15"
}
```

## SLA de triage

Baseline versionado en `policy.json`:

- critical: 24 h;
- high: 72 h;
- medium: 14 días;
- low: 30 días.

El reloj parte de la primera detección real del proyecto. CI incluye el SLA aplicable en cada finding, pero no inventa la fecha de primera detección; esa evidencia vive en el registro de triage.

## Licencias

`license-policy.json` empieza sin denylist universal. Hache Base no toma decisiones legales por todos los proyectos.

- `report_missing=true`: metadata de licencia ausente se reporta para revisión humana;
- `denied`: lista explícita de identificadores/licencias que el proyecto decidió no aceptar;
- `block_denied=true`: coincidencias con esa lista bloquean en modo `block`;
- `block_missing=false` por default: ausencia de metadata no se convierte automáticamente en conclusión legal;
- yarn/pnpm sin parser integrado generan `license_not_evaluated` y un estado explícito `NOT EVALUATED`.

## Exit codes

- `0`: ejecución válida sin blockers aplicados por el modo actual; revisar `evidence_complete` antes de interpretar el resultado;
- `1`: existen findings bloqueantes bajo el modo/nivel actual;
- `2`: configuración/entrada inválida y no hay evidencia confiable.

## Promoción recomendada

1. `report` para inventario inicial;
2. resolver falsos positivos/stack roots y documentar riesgos;
3. `baseline` para secretos + lockfiles;
4. completar SCA/licencias con el stack real hasta `evidence_complete=true`;
5. `block` en B/C cuando el equipo pueda sostener triage/SLA y mitigaciones explícitas.

No promover un release ocultando `sca_unavailable` o `license_not_evaluated`; ausencia de evidencia sigue siendo ausencia de evidencia aunque no sea un blocker automático del scanner.

## Evidencia atribuible al HEAD revisado

- El secret scan evalúa el contenido y tipo versionados en el árbol de `HEAD`; no usa archivos regulares ni destinos de symlink del working tree como evidencia del commit reportado.
- Un audit npm/Composer pre-generado solo cuenta como evidencia si incluye `hache_lock_sha256` y ese SHA-256 coincide con el blob del lockfile revisado. Un reporte sin vínculo o con hash distinto queda `NOT EVALUATED`.
- Cuando el checker ejecuta `npm audit` o `composer audit`, materializa temporalmente desde `HEAD` únicamente el manifest y lockfile revisados, ejecuta allí la herramienta y elimina el temporal al terminar.
- `composer.lock` reconoce dependencias virtuales satisfechas mediante `provide`/`replace`; la validación de rangos conserva la semántica abreviada soportada por Composer, incluido `1.0 - 2.0`.
