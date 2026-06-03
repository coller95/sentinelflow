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

APP="notepad"   # fixed for now
COUNT=3         # fixed for now: apps to run inside the one desktop

PREFIX=""; NAME=""; RES="1024x768"; WORKSPACE=""; TIMEOUT=30
ENV_KV=()

die(){ echo "ERR: $*" >&2; exit 1; }
usage(){ sed -n '2,/^set -euo/p' "$0" | sed 's/^# \{0,1\}//;$d'; exit "${1:-0}"; }

while (($#)); do
  case "$1" in
    -p|--prefix)    PREFIX="${2:?}"; shift 2 ;;
    -n|--name)      NAME="${2:?}"; shift 2 ;;
    -r|--res)       RES="${2:?}"; shift 2 ;;
    -w|--workspace) WORKSPACE="${2:?}"; shift 2 ;;
    -e|--env)       ENV_KV+=("${2:?}"); shift 2 ;;
    -t|--timeout)   TIMEOUT="${2:?}"; shift 2 ;;
    -h|--help)      usage 0 ;;
    -*)             die "unknown flag '$1' (see --help)" ;;
    *)              die "unexpected arg '$1' (apps are fixed; see --help)" ;;
  esac
done

[[ -n "$PREFIX" ]] || die "need --prefix (see --help)"
[[ -d "$PREFIX" ]] || die "prefix not found: $PREFIX (run ./deploy/bootstrap.sh $PREFIX first)"
command -v wine    >/dev/null || die "wine not on PATH"
command -v xdotool >/dev/null || die "xdotool not on PATH"

NAME="${NAME:-$(basename "$PREFIX")}"
NAME="${NAME#"${NAME%%[!.]*}"}"  # strip leading dots (~/.wineTest -> wineTest)
WIN_NAME="$NAME - Wine Desktop"

# ── teardown: kill everything in this prefix, once ──
ALL_PIDS=()
cleaned=0
cleanup(){
  (($cleaned)) && return; cleaned=1
  echo; echo ">> tearing down '$NAME' ..."
  ((${#ALL_PIDS[@]})) && kill "${ALL_PIDS[@]}" 2>/dev/null || true
  # wineserver -k stops every wine process in THIS prefix in one shot
  WINEPREFIX="$PREFIX" wineserver -k 2>/dev/null || true
  echo ">> down."
}
trap cleanup INT TERM EXIT

# ── env shared by every app ──
RUN_ENV=( "WINEPREFIX=$PREFIX" )
((${#ENV_KV[@]})) && RUN_ENV+=( "${ENV_KV[@]}" )

# launch one app into the named desktop (every app uses the SAME name so they
# share one desktop window — but they must NOT race to CREATE it, so we bring
# the first one up and wait for the window before adding the rest).
run_app(){
  local n="$1" log="${TMPDIR:-/tmp}/wine-${NAME}-${1}.log"
  env "${RUN_ENV[@]}" wine explorer "/desktop=$NAME,$RES" "$APP" >"$log" 2>&1 &
  ALL_PIDS+=("$!")
  echo ">> [$n] $APP (pid=$! log=$log)"
}

echo ">> bringing up desktop '$NAME' ($RES) with $COUNT x $APP"

# ── first app: creates the desktop; wait for its window ──
run_app 1
echo ">> waiting for window: '$WIN_NAME' (<=${TIMEOUT}s)"
WID=""
for ((i=0; i<TIMEOUT*2; i++)); do
  WID="$(xdotool search --name "^${WIN_NAME}$" 2>/dev/null | head -1 || true)"
  [[ -n "$WID" ]] && break
  sleep 0.5
done
[[ -n "$WID" ]] || die "desktop window '$WIN_NAME' did not appear in ${TIMEOUT}s"
echo ">> desktop window id: $WID"

# ── remaining apps: join the now-existing desktop (no create race) ──
for ((n=2; n<=COUNT; n++)); do run_app "$n"; sleep 0.5; done

# ── park the desktop on a workspace ──
if [[ -n "$WORKSPACE" ]] && xdotool get_num_desktops >/dev/null 2>&1; then
  xdotool set_desktop_for_window "$WID" "$WORKSPACE" && echo ">> parked on workspace $WORKSPACE"
fi

echo ">> up: prefix=$PREFIX name='$NAME' window='$WIN_NAME' wid=$WID apps=$COUNT"
echo ">> supervising — Ctrl+C to stop and tear down all."

# ── block until all apps exit (or Ctrl+C) ──
wait "${ALL_PIDS[@]}"
