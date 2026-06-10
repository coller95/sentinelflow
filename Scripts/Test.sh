#!/usr/bin/env bash
set -euo pipefail
# Resolve script location and set project root
SCRIPTDIR="$(cd -- "$(dirname "$0")" >/dev/null; pwd -P)"
PROJECT_ROOT="$(dirname "$SCRIPTDIR")"
cd "$PROJECT_ROOT"

if [ -f .venv/bin/activate ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

pytest -q
