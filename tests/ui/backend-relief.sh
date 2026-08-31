#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CSS="$ROOT/src/ui/backend-relief.css"
DOC="$ROOT/docs/UI-BACKEND-RELIEF.md"

[[ -f "$CSS" ]]
[[ -f "$DOC" ]]

grep -Fq -- '--hache-control-top-edge:rgba(148,163,184,.34);' "$CSS"
grep -Fq -- '--hache-control-focus:#2563eb;' "$CSS"
grep -Fq -- 'inset 0 1px 0 rgba(255,255,255,.78)' "$CSS"
grep -Fq -- 'border-top-color:var(--hache-control-top-edge)!important;' "$CSS"
grep -Fq -- '.hache-control:not(.hache-control--flat){' "$CSS"
grep -Fq -- '.hache-control.hache-control--primary:not(.hache-control--flat){' "$CSS"
grep -Fq -- 'outline:3px solid var(--hache-control-focus)!important;' "$CSS"
grep -Fq -- '@media(hover:hover)' "$CSS"
grep -Fq -- '.hache-control:not(.hache-control--flat):disabled:hover{' "$CSS"
grep -Fq -- '@media(max-width:750px)' "$CSS"
grep -Fq -- '@media(hover:none)' "$CSS"
grep -Fq -- '@media(prefers-reduced-motion:reduce)' "$CSS"

# La variante flat debe excluir el relieve, no borrar estilos propios del componente.
! grep -Fq -- '.hache-control--flat,' "$CSS"
! grep -Fq -- 'border:0!important;' "$CSS"

grep -Fq -- 'El borde superior **no debe ser blanco puro**' "$DOC"
grep -Fq -- 'No aplicar `.hache-control` indiscriminadamente' "$DOC"
grep -Fq -- 'no sobrescribe borde, sombra, `transform` ni `filter`' "$DOC"
grep -Fq -- 'contraste mínimo de 3:1' "$DOC"

echo "BACKEND_RELIEF_UI_OK"
