#!/usr/bin/env bash
# launch.sh — run one or more app instances in a wine prefix as named,
# capturable windows and SUPERVISE them. The script stays in the foreground;
# Ctrl+C (or any exit) tears down EVERYTHING it spawned (all instances + the
# prefix's wineserver), so nothing is left behind.
#
# The app is fixed (notepad for now) — not a user choice yet.
# Bootstrap the prefix first:  ./deploy/bootstrap.sh <PREFIX>
#
# Instances come in two roles:
#   fg  the script WAITS on these — when all fg instances exit, the script
#       exits (and teardown then kills any bg instances too).
#   bg  spawned alongside, not waited on, but still killed at teardown.
# With no fg instances the script blocks until Ctrl+C.
#
# Usage:
#   ./deploy/launch.sh -p <PREFIX> [options]
#
# Options:
#   -p, --prefix DIR     WINEPREFIX to run in (required)
#       --fg N           number of foreground instances (default: 1)
#       --bg N           number of background instances (default: 0)
#   -n, --name NAME      base window/desktop name (default: basename of PREFIX)
#   -r, --res WxH        virtual-desktop size (default: 1024x768)
#   -w, --workspace N    park every window on EWMH workspace N (0-indexed)
#   -f, --fullscreen     run native (no wine virtual desktop)
#   -e, --env K=V        extra env var for every instance (repeatable)
#   -t, --timeout SEC    seconds to wait for each window (default: 30)
#   -h, --help           this help
set -euo pipefail

APP="notepad"   # fixed for now

PREFIX=""; NAME=""; RES="1024x768"; WORKSPACE=""; FULLSCREEN=0; TIMEOUT=30
FG=1; BG=0; ENV_KV=()

die(){ echo "ERR: $*" >&2; exit 1; }
usage(){ sed -n '2,/^set -euo/p' "$0" | sed 's/^# \{0,1\}//;$d'; exit "${1:-0}"; }

while (($#)); do
  case "$1" in
    -p|--prefix)    PREFIX="${2:?}"; shift 2 ;;
    --fg)           FG="${2:?}"; shift 2 ;;
    --bg)           BG="${2:?}"; shift 2 ;;
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
[[ "$FG" =~ ^[0-9]+$ && "$BG" =~ ^[0-9]+$ ]] || die "--fg/--bg must be integers"
(( FG + BG > 0 )) || die "nothing to launch (--fg and --bg are both 0)"
command -v wine    >/dev/null || die "wine not on PATH"
command -v xdotool >/dev/null || die "xdotool not on PATH"

NAME="${NAME:-$(basename "$PREFIX")}"
NAME="${NAME#"${NAME%%[!.]*}"}"  # strip leading dots (~/.wineTest -> wineTest)

# ── teardown: kill everything we spawned, once ──
ALL_PIDS=()
cleaned=0
cleanup(){
  (($cleaned)) && return; cleaned=1
  echo; echo ">> tearing down (${#ALL_PIDS[@]} instances) ..."
  ((${#ALL_PIDS[@]})) && kill "${ALL_PIDS[@]}" 2>/dev/null || true
  # wineserver -k stops every wine process in THIS prefix in one shot
  WINEPREFIX="$PREFIX" wineserver -k 2>/dev/null || true
  echo ">> down."
}
trap cleanup INT TERM EXIT

# ── env shared by every instance ──
RUN_ENV=( "WINEPREFIX=$PREFIX" )
((${#ENV_KV[@]})) && RUN_ENV+=( "${ENV_KV[@]}" )

# spawn one instance: $1=role(fg|bg) $2=index -> echoes nothing, sets globals
FG_PIDS=()
spawn(){
  local role="$1" idx="$2" iname winname pid log
  iname="${NAME}-${role}${idx}"
  log="${TMPDIR:-/tmp}/wine-${iname}.log"
  if ((FULLSCREEN)); then
    env "${RUN_ENV[@]}" wine "$APP" >"$log" 2>&1 &
    winname="$iname"
  else
    env "${RUN_ENV[@]}" wine explorer "/desktop=$iname,$RES" "$APP" >"$log" 2>&1 &
    winname="$iname - Wine Desktop"
  fi
  pid=$!
  ALL_PIDS+=("$pid")
  [[ "$role" == fg ]] && FG_PIDS+=("$pid")
  echo ">> [$role $idx] launched $APP -> '$winname' (pid=$pid, log=$log)"

  # wait for the window, then optionally park it
  local wid="" i
  for ((i=0; i<TIMEOUT*2; i++)); do
    wid="$(xdotool search --name "^${winname}$" 2>/dev/null | head -1 || true)"
    [[ -n "$wid" ]] && break
    kill -0 "$pid" 2>/dev/null || { echo ">> [$role $idx] ERR: wine exited early (see $log)" >&2; return; }
    sleep 0.5
  done
  [[ -n "$wid" ]] || { echo ">> [$role $idx] WARN: window not seen in ${TIMEOUT}s (see $log)" >&2; return; }
  echo ">> [$role $idx] window id: $wid"
  if [[ -n "$WORKSPACE" ]] && xdotool get_num_desktops >/dev/null 2>&1; then
    xdotool set_desktop_for_window "$wid" "$WORKSPACE" && echo ">> [$role $idx] parked on workspace $WORKSPACE"
  fi
}

# ── spawn all instances ──
for ((n=1; n<=FG; n++)); do spawn fg "$n"; done
for ((n=1; n<=BG; n++)); do spawn bg "$n"; done

echo ">> up: prefix=$PREFIX  fg=$FG bg=$BG  total=${#ALL_PIDS[@]}"
echo ">> supervising — Ctrl+C to stop and tear down all."

# ── block: wait on fg instances (or all, if there are no fg) ──
if ((${#FG_PIDS[@]})); then
  wait "${FG_PIDS[@]}"
else
  wait "${ALL_PIDS[@]}"
fi
