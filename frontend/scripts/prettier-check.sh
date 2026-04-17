#!/usr/bin/env bash
# Pre-commit wrapper: runs prettier --check from the frontend/ directory so that
# plugin resolution (prettier-plugin-tailwindcss) picks up frontend/node_modules.
# Pre-commit passes files relative to the repo root (e.g. frontend/src/app/page.tsx);
# strip the leading frontend/ before invoking prettier inside the frontend workspace.
set -euo pipefail

if [[ $# -eq 0 ]]; then
  exit 0
fi

rel_files=()
for f in "$@"; do
  rel_files+=("${f#frontend/}")
done

cd "$(dirname "$0")/.."
exec node node_modules/prettier/bin/prettier.cjs --check "${rel_files[@]}"
