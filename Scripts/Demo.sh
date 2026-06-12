#!/usr/bin/env bash
# Demo.sh — end-to-end smoke demo of the wine isolation env.
#
# Launches ONE headless instance (deploy/launch.sh --xvfb) carrying the real
# node (Scripts/RunNode.sh), waits for the desktop window + node HTTP, then
# drives EVERYTHING through the node's own API — the same path the
# orchestrator uses in production: click + keystrokes via /api/control/*
# (services -> linux_handler focus+XTEST) and the proof screenshot via
# /api/capture/latest. No direct xdotool: the demo proves the system, not
# the tools. Tears the instance down at the end and verifies nothing was
# left behind.
#
# Usage:
#   Scripts/Demo.sh [-p PREFIX] [-m MESSAGE] [-o PNG] [-X] [-s SECS]
#     -p PREFIX   bootstrapped wine prefix to launch from (default ~/.wine)
#     -m MESSAGE  text typed into notepad
#     -o PNG      where the proof screenshot lands (default /tmp/wine-demo.png)
#     -X          show on your real display: skip Xvfb and run the wine
#                 desktop on the current $DISPLAY (briefly steals mouse +
#                 focus while it clicks and types)
#     -s SECS     hold the instance up that long after typing, before
#                 teardown (default: 10 with -X so you can watch, else 0)
set -euo pipefail

SCRIPTDIR="$(cd -- "$(dirname "$0")" >/dev/null; pwd -P)"
PROJECT_ROOT="$(dirname "$SCRIPTDIR")"
cd "$PROJECT_ROOT"

PREFIX="$HOME/.wine"
MSG='hello from claude! scripted wine demo works :)'
OUT=/tmp/wine-demo.png
ONDISPLAY=0
HOLD=''
while getopts 'p:m:o:Xs:h' opt; do
  case "$opt" in
    p) PREFIX=$OPTARG ;;
    m) MSG=$OPTARG ;;
    o) OUT=$OPTARG ;;
    X) ONDISPLAY=1 ;;
    s) HOLD=$OPTARG ;;
    *) sed -n '2,23p' "$0"; exit 0 ;;
  esac
done
shift $((OPTIND - 1))
# getopts stops at the first non-option word, silently dropping every flag
# after it ('Demo.sh foo -X' would run headless) — refuse stray args instead.
[[ $# -eq 0 ]] || { echo "!! unexpected argument(s): $*"; sed -n '2,23p' "$0"; exit 1; }
[[ -z "$HOLD" ]] && HOLD=$(( ONDISPLAY ? 10 : 0 ))
[[ "$HOLD" =~ ^[0-9]+$ ]] || { echo "!! -s wants a number of seconds, got '$HOLD'"; exit 1; }

LAUNCH_OPTS=(--xvfb)
if (( ONDISPLAY )); then
  [[ -n "${DISPLAY:-}" ]] || { echo "!! -X needs \$DISPLAY set"; exit 1; }
  LAUNCH_OPTS=()
fi

# /api/control/key takes ONE key per call. The node resolves named special
# keys (space, enter, ...) via its own map and passes any single visible
# char straight to xdotool as a literal keysym — so punctuation goes through
# AS THE CHARACTER, not as a name ('colon' would be rejected as unknown).
keysym(){
  case "$1" in
    ' ') echo space ;;
    '"'|'\') return 1 ;;   # would need JSON escaping; not worth it here
    *) printf '%s' "$1" ;;
  esac
}
# Validate up front, before anything launches.
for ((i = 0; i < ${#MSG}; i++)); do
  keysym "${MSG:i:1}" >/dev/null || { echo "!! no keysym mapping for '${MSG:i:1}' — extend keysym() or change -m"; exit 1; }
done

LOG="$(mktemp /tmp/wine-demo-launch.XXXXXX.log)"

echo ">> launching instance (prefix=$PREFIX, log=$LOG)"
./deploy/launch.sh -p "$PREFIX" -c 1 "${LAUNCH_OPTS[@]}" --node-cmd Scripts/RunNode.sh >"$LOG" 2>&1 &
LAUNCHER=$!
# Safety net only — the happy path tears down explicitly below.
# TERM, not INT: a backgrounded launch.sh starts with SIGINT ignored
# (non-interactive shell + &), and bash cannot trap a signal that was
# ignored at entry — an INT would be silently dropped.
cleanup(){ kill -TERM "$LAUNCHER" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

# The launcher prints '>> up: ...' once the window is mapped and the node is
# spawned; everything we need next (window title, member pids) is in the log.
for _ in $(seq 1 60); do
  grep -q '^>> up:' "$LOG" && break
  kill -0 "$LAUNCHER" 2>/dev/null || { echo "!! launcher died during startup:"; cat "$LOG"; exit 1; }
  sleep 1
done
grep -q '^>> up:' "$LOG" || { echo "!! timeout waiting for instance:"; cat "$LOG"; exit 1; }

WIN="$(sed -n "s/^>> up:.*window='\([^']*\)'.*/\1/p" "$LOG")"
NODE_LOG="$(sed -n 's/^>> \[node\] pid=[0-9]\+ log=\(.*\)/\1/p' "$LOG")"
echo ">> instance up: window='$WIN'"

# Node up? RunNode.sh logs its base URL; poll /api/server/info until it answers.
NODE_URL=''
for _ in $(seq 1 30); do
  NODE_URL="$(sed -n 's|^>> sentinelflow node.*: \(http://[0-9.:]\+\) .*|\1|p' "$NODE_LOG" 2>/dev/null | tail -1)"
  [[ -n "$NODE_URL" ]] && curl -fsS -m 1 "$NODE_URL/api/server/info" >/dev/null 2>&1 && break
  sleep 1
done
[[ -n "$NODE_URL" ]] || { echo "!! node never came up:"; cat "$NODE_LOG" 2>/dev/null; exit 1; }
echo ">> node answering: $NODE_URL/api/server/info -> $(curl -fsS -m 2 "$NODE_URL/api/server/info")"

api(){ # api METHOD PATH [JSON]
  if [[ $# -ge 3 ]]; then
    curl -fsS -m 5 -X "$1" "$NODE_URL$2" -H 'Content-Type: application/json' -d "$3"
  else
    curl -fsS -m 5 -X "$1" "$NODE_URL$2"
  fi
}

# The node auto-attaches to the wine window by the seeded title; wait for it.
for _ in $(seq 1 30); do
  api GET /api/app/status 2>/dev/null | grep -q '"attached": *true' && break
  sleep 1
done
api GET /api/app/status | grep -q '"attached": *true' \
  || { echo "!! node never attached to the wine window"; api GET /api/app/status || true; exit 1; }
echo ">> node attached to '$WIN'"

api POST /api/capture/start '{"intervalSeconds":0.5}' >/dev/null

# Click the window center (normalized coords) to land the caret in notepad's
# edit area, then send the message one keysym at a time. Both go through the
# node's control queue -> linux_handler focus+XTEST — wine drops synthetic
# XSendEvent input, XTEST is indistinguishable from a real keyboard.
api POST /api/control/click '{"x":0.5,"y":0.5}' >/dev/null
sleep 1
for ((i = 0; i < ${#MSG}; i++)); do
  api POST /api/control/key "{\"keyName\":\"$(keysym "${MSG:i:1}")\"}" >/dev/null
done
echo ">> typed via node api: '$MSG'"

# Proof straight from the node's capture pipeline. The control queue is
# async — give the worker time to drain every enqueued keystroke before
# trusting the frame (scaled to message length, ~5 keys/s worst case).
sleep $(( ${#MSG} / 5 + 2 ))
curl -fsS -m 5 "$NODE_URL/api/capture/latest?fmt=png" -o "$OUT"
echo ">> captured via node api -> $OUT"

if (( HOLD )); then
  echo ">> holding ${HOLD}s — go look at the window"
  sleep "$HOLD"
fi

# Teardown: SIGTERM the launcher (same trap path as Ctrl+C; see cleanup note
# on why not INT), then verify every member pid it reported is actually gone.
echo ">> tearing down (SIGTERM launcher pid=$LAUNCHER)"
kill -TERM "$LAUNCHER"
wait "$LAUNCHER" 2>/dev/null || true
trap - EXIT INT TERM

sleep 1
LEFT=0
for pid in $(grep -o 'pid=[0-9]\+' "$LOG" | cut -d= -f2 | sort -u); do
  if kill -0 "$pid" 2>/dev/null || [[ -e "/proc/$pid" ]]; then
    echo "!! leftover pid $pid: $(ps -o cmd= -p "$pid")"
    LEFT=1
  fi
done
(( LEFT )) && { echo "!! teardown incomplete"; exit 1; }
echo ">> teardown clean — no leftovers. proof: $OUT"
