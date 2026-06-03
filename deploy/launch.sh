#!/usr/bin/env bash
# launch.sh — GENERIC wine-fleet launcher (app-agnostic).
#
# Launches ONE wine instance from a PROFILE, parks it on an optional GNOME/EWMH
# workspace, then blocks until Ctrl+C and kills the instance. ZERO app specifics
# live here: paths, renderer, env, and args all come from the sourced PROFILE.
# Window placement lives in lib/window.sh; wine launching in lib/wine.sh.
#
# Windowed (default): APP_MAIN runs in a wine virtual desktop (/desktop=$NAME,$RES);
#   fleet waits for that window and parks it. If something else already owns that
#   desktop (e.g. apps/wc3/maphack.sh started first), APP_MAIN joins it.
# Fullscreen (-f):    APP_MAIN runs native (own X window), parked once it appears.
#
# Usage:  ./launch.sh [--fullscreen|-f] [--workspace|-w N] PROFILE PREFIX
#   PROFILE       = bash profile file (e.g. apps/wc3/config.sh), abs or rel to CWD
#   PREFIX        = wine prefix path (e.g. ~/.wineGame1)
#   --fullscreen  = run APP_MAIN native on the main screen (no wine desktop wrapper)
#   --workspace N = park this instance on GNOME/EWMH workspace N (0-indexed)
#   multiple instances = separate terminals, distinct prefixes + workspaces:
#     ./launch.sh -w 0 apps/wc3/config.sh ~/.wineGame1
#     ./launch.sh -w 1 apps/wc3/config.sh ~/.wineGame2
#
# PROFILE contract — the sourced profile MUST set:
#   APP_MAIN  windows path of main exe, e.g. 'C:\Program Files (x86)\...\war3.exe'
#   APP_ENV   bash array of NAME=VALUE env strings for the main launch (may be ())
#   APP_ARGS  bash array of extra args for the main exe               (may be ())
#   APP_RES   resolution string (optional; fleet defaults to 1024x768)
#   APP_NAME  instance name      (optional; fleet defaults to basename of PREFIX)
# PROFILE may define (fleet detects with `declare -F`):
#   app_check_prefix  preflight; print ERR + return nonzero on missing files
# fleet exports to the profile: PREFIX NAME DESK RES FULLSCREEN WORKSPACE
set -u

HERE="$(cd "$(dirname "$0")" && pwd)"

fail(){ echo "ERR: $*" >&2; cleanup; }

cleanup(){
  echo; echo ">> [$NAME] Ctrl+C — killing $NAME"
  WINEPREFIX="$PREFIX" wineserver -k 2>/dev/null
  exit 0
}

# ---- flags: --fullscreen/-f, --workspace/-w N (before positionals) ----
FULLSCREEN="${FULLSCREEN:-0}"
WORKSPACE="${WORKSPACE:-}"
while :; do case "${1:-}" in
  --fullscreen|-f) FULLSCREEN=1; shift ;;
  --workspace|-w)  WORKSPACE="${2:-}"; shift 2 ;;
  --) shift; break ;;
  -*) echo "ERR: unknown flag '$1'" >&2; exit 2 ;;
  *) break ;;
esac; done

# ---- positionals: PROFILE PREFIX ----
PROFILE="${1:-}"
PREFIX="${2:-}"
[[ -n "$PROFILE" && -n "$PREFIX" ]] \
  || { echo "Usage: $0 [--fullscreen|-f] [--workspace|-w N] PROFILE PREFIX" >&2; exit 2; }

# Resolve PROFILE relative to CWD (or accept absolute), then source it.
case "$PROFILE" in
  /*) PROFILE_PATH="$PROFILE" ;;
  *)  PROFILE_PATH="$PWD/$PROFILE" ;;
esac
[[ -f "$PROFILE_PATH" ]] || { echo "ERR: profile not found: $PROFILE_PATH" >&2; exit 1; }

# Pre-export the env the profile may read while sourcing / in its functions.
NAME="$(basename "$PREFIX")"
DESK="$NAME - Wine Desktop"
export PREFIX NAME DESK FULLSCREEN WORKSPACE
RES="1024x768"; export RES   # provisional; finalized after sourcing

# shellcheck disable=SC1090
source "$PROFILE_PATH" || { echo "ERR: failed to source profile: $PROFILE_PATH" >&2; exit 1; }

# ---- resolve profile-provided config with fleet defaults ----
NAME="${APP_NAME:-$NAME}"
RES="${APP_RES:-1024x768}"
DESK="$NAME - Wine Desktop"
export NAME RES DESK
: "${APP_MAIN:?profile must set APP_MAIN}"
# Ensure the arrays exist even if the profile left them unset.
declare -p APP_ENV  >/dev/null 2>&1 || APP_ENV=()
declare -p APP_ARGS >/dev/null 2>&1 || APP_ARGS=()

WIN_TIMEOUT="${WIN_TIMEOUT:-20}"   # secs to wait for the wine desktop window

# ---- generic building blocks (window placement, wine launching) ----
# shellcheck source=lib/window.sh disable=SC1091
source "$HERE/lib/window.sh"
# shellcheck source=lib/wine.sh disable=SC1091
source "$HERE/lib/wine.sh"

trap cleanup INT TERM

# ---- preflight (optional) ----
if declare -F app_check_prefix >/dev/null; then
  app_check_prefix || fail "preflight failed for $PREFIX"
fi

# ---- launch ----
if [[ "$FULLSCREEN" == 1 ]]; then
  echo ">> [$NAME] launch APP_MAIN FULLSCREEN (native)"
  launch_native_main
  park_native_app
else
  echo ">> [$NAME] launch APP_MAIN in wine desktop ($NAME,$RES)"
  launch_desktop_main
  echo ">> [$NAME] wait for wine desktop window"
  wid=$(wait_win) || fail "wine desktop window not found in ${WIN_TIMEOUT}s"
  echo ">> [$NAME] desktop window = $wid"
  move_to_workspace "$wid"
fi

echo ">> [$NAME] running. Ctrl+C to kill."
wait
