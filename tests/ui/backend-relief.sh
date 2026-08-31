#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CSS="$ROOT/src/ui/backend-relief.css"
DOC="$ROOT/docs/UI-BACKEND-RELIEF.md"

[[ -f "$CSS" ]]
[[ -f "$DOC" ]]
grep -Fq -- '--hache-control-top-edge: var(--border-subtle);' "$CSS"
grep -Fq -- '--hache-control-focus: var(--color-focus);' "$CSS"
grep -Fq -- '--hache-control-duration: var(--motion-fast);' "$CSS"
grep -Fq -- 'border-block-start-color: var(--hache-control-top-edge) !important;' "$CSS"
grep -Fq -- '.hache-control:not(.hache-control--flat)' "$CSS"
grep -Fq -- '.hache-control.hache-control--primary:not(.hache-control--flat)' "$CSS"
grep -Fq -- ':focus-visible' "$CSS"
grep -Fq -- '@media (hover: hover) and (pointer: fine)' "$CSS"
grep -Fq -- '[aria-disabled="true"]' "$CSS"
grep -Fq -- '[aria-busy="true"]' "$CSS"
grep -Fq -- '[data-state="success"]' "$CSS"
grep -Fq -- '[data-state="warning"]' "$CSS"
grep -Fq -- '[data-state="error"]' "$CSS"
grep -Fq -- '@media (min-width: 46.875rem)' "$CSS"
grep -Fq -- '@media (prefers-reduced-motion: reduce)' "$CSS"
grep -Fq -- '@media (forced-colors: active)' "$CSS"
! grep -Fq -- 'border: 0 !important;' "$CSS"
! grep -Eq -- '#[0-9a-fA-F]{3,8}|rgba?\(' "$CSS"
grep -Fq -- 'No aplicar `.hache-control` indiscriminadamente' "$DOC"
grep -Fq -- 'no sobrescribe borde, sombra, `transform` ni `filter`' "$DOC"
grep -Fq -- 'contraste mínimo 3:1' "$DOC"
echo "BACKEND_RELIEF_UI_OK"
