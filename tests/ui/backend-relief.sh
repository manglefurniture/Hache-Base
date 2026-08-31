#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CSS="$ROOT/src/ui/backend-relief.css"
DOC="$ROOT/docs/UI-BACKEND-RELIEF.md"

[[ -f "$CSS" ]]
[[ -f "$DOC" ]]

grep -Fq -- '--hache-control-top-edge:rgba(148,163,184,.34);' "$CSS"
grep -Fq -- 'inset 0 1px 0 rgba(255,255,255,.78)' "$CSS"
grep -Fq -- 'border-top-color:var(--hache-control-top-edge)!important;' "$CSS"
grep -Fq -- '.hache-control--primary{' "$CSS"
grep -Fq -- 'border-top-color:rgba(255,255,255,.34)!important;' "$CSS"
grep -Fq -- '.hache-control--flat,' "$CSS"
grep -Fq -- '@media(hover:hover)' "$CSS"
grep -Fq -- '.hache-control:disabled:hover{' "$CSS"
grep -Fq -- '@media(max-width:750px)' "$CSS"
grep -Fq -- '@media(hover:none)' "$CSS"
grep -Fq -- '@media(prefers-reduced-motion:reduce)' "$CSS"

grep -Fq -- 'El borde superior **no debe ser blanco puro**' "$DOC"
grep -Fq -- 'No aplicar `.hache-control` indiscriminadamente' "$DOC"

echo "BACKEND_RELIEF_UI_OK"
