#!/usr/bin/env bash
# launch.sh — bring up ONE wine virtual desktop in a prefix and run the apps
# inside it, then SUPERVISE. The script stays in the foreground; Ctrl+C (or any
# exit) tears down EVERYTHING it spawned (all apps + the prefix's wineserver),
# so nothing is left behind.
#
# The apps are fixed for now: 3 notepad instances inside the one desktop.
# Bootstrap the prefix first:  ./deploy/bootstrap.sh <PREFIX>
#
# Usage:
#   ./deploy/launch.sh -p <PREFIX> [options]
#
# Options:
#   -p, --prefix DIR     WINEPREFIX to run in (required)
#   -n, --name NAME      desktop name (default: basename of PREFIX, dots stripped)
#   -r, --res WxH        virtual-desktop size (default: 1024x768)
#   -w, --workspace N    park the desktop on EWMH workspace N (0-indexed)
#   -e, --env K=V        extra env var for every app (repeatable)
#   -t, --timeout SEC    seconds to wait for the desktop window (default: 30)
#   -h, --help           this help
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/modules/log.sh"
source "$HERE/modules/teardown.sh"
source "$HERE/modules/cli.sh"
source "$HERE/modules/preflight.sh"
source "$HERE/modules/desktop.sh"
source "$HERE/modules/apps.sh"

parse_cli "$@"
preflight
derive_name
install_teardown
build_run_env

log "bringing up desktop '$NAME' ($RES) with $COUNT x $APP"

run_app 1
wait_for_window

for ((n=2; n<=COUNT; n++)); do run_app "$n"; sleep 0.5; done

park_workspace

echo ">> up: prefix=$PREFIX name='$NAME' window='$WIN_NAME' wid=$WID apps=$COUNT"
echo ">> supervising — Ctrl+C to stop and tear down all."

wait "${ALL_PIDS[@]}"
