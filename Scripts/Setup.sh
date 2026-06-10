#!/usr/bin/env bash
set -euo pipefail
# Resolve script location and set project root
SCRIPTDIR="$(cd -- "$(dirname "$0")" >/dev/null; pwd -P)"
PROJECT_ROOT="$(dirname "$SCRIPTDIR")"
cd "$PROJECT_ROOT"

python -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
