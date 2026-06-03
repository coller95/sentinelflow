#!/usr/bin/env bash
# fleet.sh — GENERIC wine-fleet launcher (app-agnostic).
#
# Launches ONE wine instance from a PROFILE, parks it on an optional GNOME/EWMH
# workspace, runs the profile's pre-main vision/click sequence, then blocks until
# Ctrl+C and kills the instance. ZERO app specifics live here: paths, renderer,
# env, args, and any helper/vision logic all come from the sourced PROFILE.
#
# Two launch shapes (auto-detected via `declare -F app_launch_helper`):
#   helper path  — profile launches a helper that OWNS a wine desktop
#                  (/desktop=$NAME,$RES). fleet waits for the desktop window,
#                  parks it (windowed), runs app_pre_main WID, then launches
#                  APP_MAIN into the SAME desktop (helper injects into it).
#   direct path  — no helper. fleet launches APP_MAIN itself: windowed goes into
#                  a fresh wine desktop (/desktop=$NAME,$RES); fullscreen runs
#                  APP_MAIN native and parks the app's own window once it appears.
#
# Usage:  ./fleet.sh [--fullscreen|-f] [--workspace|-w N] PROFILE PREFIX
#   PROFILE       = bash profile file (e.g. apps/wc3/profile.sh), abs or rel to CWD
#   PREFIX        = wine prefix path (e.g. ~/.wineGame1)
#   --fullscreen  = run APP_MAIN native on the main screen (no wine desktop wrapper)
#   --workspace N = park this instance on GNOME/EWMH workspace N (0-indexed)
#   multiple instances = separate terminals, distinct prefixes + workspaces:
#     ./fleet.sh -w 0 apps/wc3/profile.sh ~/.wineGame1
#     ./fleet.sh -w 1 apps/wc3/profile.sh ~/.wineGame2
#
# PROFILE contract — the sourced profile MUST set:
#   APP_MAIN  windows path of main exe, e.g. 'C:\Program Files (x86)\...\war3.exe'
#   APP_ENV   bash array of NAME=VALUE env strings for the main launch (may be ())
#   APP_ARGS  bash array of extra args for the main exe               (may be ())
#   APP_RES   resolution string (optional; fleet defaults to 1024x768)
#   APP_NAME  instance name      (optional; fleet defaults to basename of PREFIX)
# PROFILE may define (fleet detects with `declare -F`):
#   app_check_prefix  preflight; print ERR + return nonzero on missing files
#   app_launch_helper launch helper that owns the wine desktop (see above)
#   app_pre_main      $1 = window id; vision/click sequence (default: no-op)
# fleet exports to the profile: PREFIX NAME DESK RES FULLSCREEN WORKSPACE
set -u

fail(){ echo "ERR: $*" >&2; cleanup; }

cleanup(){
  echo; echo ">> [$NAME] Ctrl+C — killing $NAME"
  WINEPREFIX="$PREFIX" wineserver -k 2>/dev/null
  exit 0
}

find_win(){ xdotool search --name "$DESK" 2>/dev/null | head -1; }

# Fullscreen APP_MAIN renders native (no wine desktop), so it has its own X
# window distinct from $DESK. Wait for the first new wine window and park it.
# No-op if WORKSPACE unset.
park_native_app(){
  [[ -n "$WORKSPACE" ]] || return 0
  local w end=$((SECONDS + WIN_TIMEOUT))
  while [[ $SECONDS -lt $end ]]; do
    w=$(xdotool search --class wine 2>/dev/null | tail -1)
    [[ -n "$w" ]] && { move_to_workspace "$w"; return 0; }
    sleep 0.5
  done
  echo ">> [$NAME] WARN: native app window not found to park in ${WIN_TIMEOUT}s"
}

# Park a window on workspace $WORKSPACE. No-op if WORKSPACE unset; numeric guard.
# Needs an EWMH-aware WM (GNOME/mutter); harmless warning otherwise.
move_to_workspace(){
  local win="$1"
  [[ -n "$WORKSPACE" ]] || return 0
  [[ "$WORKSPACE" =~ ^[0-9]+$ ]] \
    || { echo ">> [$NAME] WARN: WORKSPACE='$WORKSPACE' not a number, skipping"; return 0; }
  if xdotool set_desktop_for_window "$win" "$WORKSPACE" 2>/dev/null; then
    echo ">> [$NAME] parked window $win on workspace $WORKSPACE"
  else
    echo ">> [$NAME] WARN: could not move window $win to workspace $WORKSPACE (no EWMH WM?)"
  fi
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
RES=""              # profile may set APP_RES; resolved below
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

trap cleanup INT TERM

# ---- preflight (optional) ----
if declare -F app_check_prefix >/dev/null; then
  app_check_prefix || fail "preflight failed for $PREFIX"
fi

WIN_TIMEOUT="${WIN_TIMEOUT:-20}"   # secs to wait for the wine desktop window

# ---------------------------------------------------------------------------
if declare -F app_launch_helper >/dev/null; then
  # ---- HELPER PATH: helper owns the wine desktop; APP_MAIN injects into it ----
  echo ">> [$NAME] launch helper (owns wine desktop $NAME,$RES)"
  app_launch_helper || fail "helper launch failed"

  echo ">> [$NAME] wait for wine desktop window"
  end=$((SECONDS + WIN_TIMEOUT)); wid=""
  while [[ $SECONDS -lt $end ]]; do wid=$(find_win); [[ -n $wid ]] && break; sleep 0.5; done
  [[ -n $wid ]] || fail "wine desktop window not found in ${WIN_TIMEOUT}s"
  echo ">> [$NAME] desktop window = $wid"

  # Windowed: APP_MAIN joins this same desktop window, so parking it now moves
  # the whole instance. (Fullscreen APP_MAIN is parked separately below.)
  [[ "$FULLSCREEN" == 1 ]] || move_to_workspace "$wid"

  if declare -F app_pre_main >/dev/null; then
    echo ">> [$NAME] run pre-main sequence"
    app_pre_main "$wid" || fail "pre-main sequence failed"
  fi

  if [[ "$FULLSCREEN" == 1 ]]; then
    echo ">> [$NAME] launch APP_MAIN FULLSCREEN (native, same prefix)"
    env WINEPREFIX="$PREFIX" "${APP_ENV[@]}" \
      wine "$APP_MAIN" "${APP_ARGS[@]}" >"$PREFIX/app.log" 2>&1 &
    park_native_app
  else
    echo ">> [$NAME] launch APP_MAIN in wine desktop (same prefix)"
    env WINEPREFIX="$PREFIX" "${APP_ENV[@]}" \
      wine explorer "/desktop=$NAME,$RES" \
      "$APP_MAIN" "${APP_ARGS[@]}" >"$PREFIX/app.log" 2>&1 &
  fi
else
  # ---- DIRECT PATH: fleet launches APP_MAIN itself ----
  if [[ "$FULLSCREEN" == 1 ]]; then
    echo ">> [$NAME] launch APP_MAIN FULLSCREEN (native)"
    env WINEPREFIX="$PREFIX" "${APP_ENV[@]}" \
      wine "$APP_MAIN" "${APP_ARGS[@]}" >"$PREFIX/app.log" 2>&1 &
    park_native_app
  else
    echo ">> [$NAME] launch APP_MAIN in wine desktop ($NAME,$RES)"
    env WINEPREFIX="$PREFIX" "${APP_ENV[@]}" \
      wine explorer "/desktop=$NAME,$RES" \
      "$APP_MAIN" "${APP_ARGS[@]}" >"$PREFIX/app.log" 2>&1 &

    echo ">> [$NAME] wait for wine desktop window"
    end=$((SECONDS + WIN_TIMEOUT)); wid=""
    while [[ $SECONDS -lt $end ]]; do wid=$(find_win); [[ -n $wid ]] && break; sleep 0.5; done
    [[ -n $wid ]] || fail "wine desktop window not found in ${WIN_TIMEOUT}s"
    echo ">> [$NAME] desktop window = $wid"
    move_to_workspace "$wid"

    if declare -F app_pre_main >/dev/null; then
      echo ">> [$NAME] run pre-main sequence"
      app_pre_main "$wid" || fail "pre-main sequence failed"
    fi
  fi
fi

echo ">> [$NAME] running. Ctrl+C to kill."
wait
