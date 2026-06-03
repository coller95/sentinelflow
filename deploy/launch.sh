#!/usr/bin/env bash
# launch.sh — run the app in a wine prefix as a named, capturable window and
# SUPERVISE it: the script stays in the foreground; Ctrl+C (or any exit) tears
# down everything it spawned (the app + the prefix's wineserver).
#
# The app is fixed (notepad for now) — not a user choice yet.
# Bootstrap the prefix first:  ./deploy/bootstrap.sh <PREFIX>
#
# Usage:
#   ./deploy/launch.sh -p <PREFIX> [options]
#
# Options:
#   -p, --prefix DIR     WINEPREFIX to run in (required)
#   -n, --name NAME      window/desktop name (default: basename of PREFIX, dots stripped)
#   -r, --res WxH        virtual-desktop size (default: 1024x768)
#   -w, --workspace N    park the window on EWMH workspace N (0-indexed)
#   -f, --fullscreen     run native (no wine virtual desktop)
#   -e, --env K=V        extra env var for the launch (repeatable)
#   -t, --timeout SEC    seconds to wait for the window (default: 30)
#   -h, --help           this help
set -euo pipefail

APP="notepad"   # fixed for now

PREFIX=""; NAME=""; RES="1024x768"; WORKSPACE=""; FULLSCREEN=0; TIMEOUT=30
ENV_KV=()

die(){ echo "ERR: $*" >&2; exit 1; }
usage(){ sed -n '2,/^set -euo/p' "$0" | sed 's/^# \{0,1\}//;$d'; exit "${1:-0}"; }

while (($#)); do
  case "$1" in
    -p|--prefix)    PREFIX="${2:?}"; shift 2 ;;
    -n|--name)      NAME="${2:?}"; shift 2 ;;
    -r|--res)       RES="${2:?}"; shift 2 ;;
    -w|--workspace) WORKSPACE="${2:?}"; shift 2 ;;
    -f|--fullscreen) FULLSCREEN=1; shift ;;
    -e|--env)       ENV_KV+=("${2:?}"); shift 2 ;;
    -t|--timeout)   TIMEOUT="${2:?}"; shift 2 ;;
    -h|--help)      usage 0 ;;
    -*)             die "unknown flag '$1' (see --help)" ;;
    *)              die "unexpected arg '$1' (the app is fixed; see --help)" ;;
  esac
done

[[ -n "$PREFIX" ]] || die "need --prefix (see --help)"
[[ -d "$PREFIX" ]] || die "prefix not found: $PREFIX (run ./deploy/bootstrap.sh $PREFIX first)"
command -v wine    >/dev/null || die "wine not on PATH"
command -v xdotool >/dev/null || die "xdotool not on PATH"

NAME="${NAME:-$(basename "$PREFIX")}"
NAME="${NAME#"${NAME%%[!.]*}"}"  # strip leading dots (~/.wineTest -> wineTest)

# ── teardown: kill what we spawned, once ──
WINE_PID=""
cleaned=0
cleanup(){
  (($cleaned)) && return; cleaned=1
  echo; echo ">> tearing down '$NAME' ..."
  [[ -n "$WINE_PID" ]] && kill "$WINE_PID" 2>/dev/null || true
  # wineserver -k stops every wine process in THIS prefix (the app + helpers)
  WINEPREFIX="$PREFIX" wineserver -k 2>/dev/null || true
  echo ">> down."
}
trap cleanup INT TERM EXIT

# ── build env ──
RUN_ENV=( "WINEPREFIX=$PREFIX" )
((${#ENV_KV[@]})) && RUN_ENV+=( "${ENV_KV[@]}" )

# ── spawn (app stdout/stderr -> logfile; we keep the PID and supervise) ──
WINE_LOG="${TMPDIR:-/tmp}/wine-${NAME}.log"
if ((FULLSCREEN)); then
  echo ">> launch (native): $APP"
  env "${RUN_ENV[@]}" wine "$APP" >"$WINE_LOG" 2>&1 &
  WIN_NAME="$NAME"
else
  echo ">> launch (desktop '$NAME', $RES): $APP"
  env "${RUN_ENV[@]}" wine explorer "/desktop=$NAME,$RES" "$APP" >"$WINE_LOG" 2>&1 &
  WIN_NAME="$NAME - Wine Desktop"
fi
WINE_PID=$!
echo ">> wine log: $WINE_LOG"

# ── wait for the window ──
echo ">> waiting for window: '$WIN_NAME' (<=${TIMEOUT}s)"
WID=""
for ((i=0; i<TIMEOUT*2; i++)); do
  WID="$(xdotool search --name "^${WIN_NAME}$" 2>/dev/null | head -1 || true)"
  [[ -n "$WID" ]] && break
  kill -0 "$WINE_PID" 2>/dev/null || die "wine exited before window appeared (see $WINE_LOG)"
  sleep 0.5
done
[[ -n "$WID" ]] || die "window '$WIN_NAME' did not appear in ${TIMEOUT}s (see $WINE_LOG)"
echo ">> window id: $WID"

# ── park on workspace ──
if [[ -n "$WORKSPACE" ]]; then
  if xdotool get_num_desktops >/dev/null 2>&1; then
    xdotool set_desktop_for_window "$WID" "$WORKSPACE"
    echo ">> parked on workspace $WORKSPACE"
  else
    echo ">> WARN: no EWMH workspaces (no WM?); ignoring --workspace $WORKSPACE" >&2
  fi
fi

echo ">> up: prefix=$PREFIX name='$NAME' window='$WIN_NAME' wid=$WID pid=$WINE_PID"
echo ">> supervising — Ctrl+C to stop and tear down."

# ── block until the app exits or we're interrupted; trap cleans up ──
wait "$WINE_PID"
