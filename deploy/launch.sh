#!/usr/bin/env bash
# launch.sh — run one or more app instances in a wine prefix as named,
# capturable windows and SUPERVISE them. Every instance runs inside its own
# wine virtual desktop. The script stays in the foreground; Ctrl+C (or any
# exit) tears down EVERYTHING it spawned (all instances + the prefix's
# wineserver), so nothing is left behind.
#
# The app is fixed (notepad for now) — not a user choice yet.
# Bootstrap the prefix first:  ./deploy/bootstrap.sh <PREFIX>
#
# Usage:
#   ./deploy/launch.sh -p <PREFIX> [options]
#
# Options:
#   -p, --prefix DIR     WINEPREFIX to run in (required)
#   -c, --count N        number of instances to run (default: 1)
#   -n, --name NAME      base window/desktop name (default: basename of PREFIX)
#   -r, --res WxH        virtual-desktop size (default: 1024x768)
#   -w, --workspace N    park every window on EWMH workspace N (0-indexed)
#   -e, --env K=V        extra env var for every instance (repeatable)
#   -t, --timeout SEC    seconds to wait for each window (default: 30)
#   -h, --help           this help
set -euo pipefail

APP="notepad"   # fixed for now

PREFIX=""; NAME=""; RES="1024x768"; WORKSPACE=""; TIMEOUT=30
COUNT=1; ENV_KV=()

die(){ echo "ERR: $*" >&2; exit 1; }
usage(){ sed -n '2,/^set -euo/p' "$0" | sed 's/^# \{0,1\}//;$d'; exit "${1:-0}"; }

while (($#)); do
  case "$1" in
    -p|--prefix)    PREFIX="${2:?}"; shift 2 ;;
    -c|--count)     COUNT="${2:?}"; shift 2 ;;
    -n|--name)      NAME="${2:?}"; shift 2 ;;
    -r|--res)       RES="${2:?}"; shift 2 ;;
    -w|--workspace) WORKSPACE="${2:?}"; shift 2 ;;
    -e|--env)       ENV_KV+=("${2:?}"); shift 2 ;;
    -t|--timeout)   TIMEOUT="${2:?}"; shift 2 ;;
    -h|--help)      usage 0 ;;
    -*)             die "unknown flag '$1' (see --help)" ;;
    *)              die "unexpected arg '$1' (the app is fixed; see --help)" ;;
  esac
done

[[ -n "$PREFIX" ]] || die "need --prefix (see --help)"
[[ -d "$PREFIX" ]] || die "prefix not found: $PREFIX (run ./deploy/bootstrap.sh $PREFIX first)"
[[ "$COUNT" =~ ^[0-9]+$ ]] && ((COUNT > 0)) || die "--count must be a positive integer"
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

# spawn one instance: $1=index. Each gets its own wine virtual desktop.
spawn(){
  local idx="$1" iname winname pid log wid i
  iname="${NAME}-${idx}"
  winname="$iname - Wine Desktop"
  log="${TMPDIR:-/tmp}/wine-${iname}.log"
  env "${RUN_ENV[@]}" wine explorer "/desktop=$iname,$RES" "$APP" >"$log" 2>&1 &
  pid=$!
  ALL_PIDS+=("$pid")
  echo ">> [$idx] launched $APP -> '$winname' (pid=$pid, log=$log)"

  # wait for the window, then optionally park it
  for ((i=0; i<TIMEOUT*2; i++)); do
    wid="$(xdotool search --name "^${winname}$" 2>/dev/null | head -1 || true)"
    [[ -n "$wid" ]] && break
    kill -0 "$pid" 2>/dev/null || { echo ">> [$idx] ERR: wine exited early (see $log)" >&2; return; }
    sleep 0.5
  done
  [[ -n "$wid" ]] || { echo ">> [$idx] WARN: window not seen in ${TIMEOUT}s (see $log)" >&2; return; }
  echo ">> [$idx] window id: $wid"
  if [[ -n "$WORKSPACE" ]] && xdotool get_num_desktops >/dev/null 2>&1; then
    xdotool set_desktop_for_window "$wid" "$WORKSPACE" && echo ">> [$idx] parked on workspace $WORKSPACE"
  fi
}

# ── spawn all instances ──
for ((n=1; n<=COUNT; n++)); do spawn "$n"; done

echo ">> up: prefix=$PREFIX  count=$COUNT  total=${#ALL_PIDS[@]}"
echo ">> supervising — Ctrl+C to stop and tear down all."

# ── block until all instances exit (or Ctrl+C) ──
wait "${ALL_PIDS[@]}"
