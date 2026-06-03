#!/usr/bin/env bash
# launch.sh — single entry point: run an exe in a wine prefix as a named,
# capturable window, optionally parked on its own GNOME/EWMH workspace.
#
# Bootstrap the prefix first:  ./bootstrap.sh <PREFIX>
#
# Usage:
#   ./launch.sh -p <PREFIX> [options] -- <exe> [exe args...]
#
# Options:
#   -p, --prefix DIR     WINEPREFIX to run in (required)
#   -n, --name NAME      window/desktop name (default: basename of PREFIX)
#   -r, --res WxH        virtual-desktop size (default: 1024x768)
#   -w, --workspace N    park the window on EWMH workspace N (0-indexed)
#   -f, --fullscreen     run native (no wine virtual desktop)
#   -e, --env K=V        extra env var for the launch (repeatable)
#   -t, --timeout SEC    seconds to wait for the window (default: 30)
#   -h, --help           this help
#
# Window: in virtual-desktop mode the title is "<NAME> - Wine Desktop";
# SentinelFlow attaches to that title, then captures/injects window-targeted.
set -euo pipefail

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
    --)             shift; break ;;
    -*)             die "unknown flag '$1' (see --help)" ;;
    *)              break ;;
  esac
done

[[ -n "$PREFIX" ]] || die "need --prefix (see --help)"
(($#)) || die "need an exe after -- (e.g. -- notepad)"
[[ -d "$PREFIX" ]] || die "prefix not found: $PREFIX (run ./bootstrap.sh $PREFIX first)"
command -v wine    >/dev/null || die "wine not on PATH"
command -v xdotool >/dev/null || die "xdotool not on PATH"

NAME="${NAME:-$(basename "$PREFIX")}"
EXE="$1"; shift
EXE_ARGS=("$@")

# ── build env ──
RUN_ENV=( "WINEPREFIX=$PREFIX" )
((${#ENV_KV[@]})) && RUN_ENV+=( "${ENV_KV[@]}" )

# ── spawn ──
if ((FULLSCREEN)); then
  echo ">> launch (native): $EXE ${EXE_ARGS[*]}"
  env "${RUN_ENV[@]}" wine "$EXE" "${EXE_ARGS[@]}" &
  WIN_NAME="$NAME"
else
  echo ">> launch (desktop '$NAME', $RES): $EXE ${EXE_ARGS[*]}"
  env "${RUN_ENV[@]}" wine explorer "/desktop=$NAME,$RES" "$EXE" "${EXE_ARGS[@]}" &
  WIN_NAME="$NAME - Wine Desktop"
fi
WINE_PID=$!

# ── wait for the window ──
echo ">> waiting for window: '$WIN_NAME' (<=${TIMEOUT}s)"
WID=""
for ((i=0; i<TIMEOUT*2; i++)); do
  WID="$(xdotool search --name "^${WIN_NAME}$" 2>/dev/null | head -1 || true)"
  [[ -n "$WID" ]] && break
  kill -0 "$WINE_PID" 2>/dev/null || die "wine exited before window appeared"
  sleep 0.5
done
[[ -n "$WID" ]] || die "window '$WIN_NAME' did not appear in ${TIMEOUT}s"
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
