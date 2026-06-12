#!/usr/bin/env bash
# Demo.sh — end-to-end smoke demo of the wine isolation env.
#
# Launches ONE headless instance (deploy/launch.sh --xvfb) carrying the real
# node (Scripts/RunNode.sh), waits for the desktop window + node HTTP, types a
# message into the notepad inside the wine desktop via XTEST (the same
# delivery path Src/infrastructure/os/linux_handler.py uses), captures the
# window with the repo's own LinuxScreenCapturer, then tears the instance
# down and verifies nothing was left behind.
#
# Usage:
#   Scripts/Demo.sh [-p PREFIX] [-m MESSAGE] [-o PNG]
#     -p PREFIX   bootstrapped wine prefix to launch from (default ~/.wine)
#     -m MESSAGE  text typed into notepad
#     -o PNG      where the proof screenshot lands (default /tmp/wine-demo.png)
set -euo pipefail

SCRIPTDIR="$(cd -- "$(dirname "$0")" >/dev/null; pwd -P)"
PROJECT_ROOT="$(dirname "$SCRIPTDIR")"
cd "$PROJECT_ROOT"

PREFIX="$HOME/.wine"
MSG='hello from claude! scripted wine demo works :)'
OUT=/tmp/wine-demo.png
while getopts 'p:m:o:h' opt; do
  case "$opt" in
    p) PREFIX=$OPTARG ;;
    m) MSG=$OPTARG ;;
    o) OUT=$OPTARG ;;
    *) sed -n '2,16p' "$0"; exit 0 ;;
  esac
done

LOG="$(mktemp /tmp/wine-demo-launch.XXXXXX.log)"

echo ">> launching instance (prefix=$PREFIX, log=$LOG)"
./deploy/launch.sh -p "$PREFIX" -c 1 --xvfb --node-cmd Scripts/RunNode.sh >"$LOG" 2>&1 &
LAUNCHER=$!
# Safety net only — the happy path tears down explicitly below.
# TERM, not INT: a backgrounded launch.sh starts with SIGINT ignored
# (non-interactive shell + &), and bash cannot trap a signal that was
# ignored at entry — an INT would be silently dropped.
cleanup(){ kill -TERM "$LAUNCHER" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

# The launcher prints '>> up: ...' once the window is mapped and the node is
# spawned; everything we need next (display, window title, member pids) is in
# the log by then.
for _ in $(seq 1 60); do
  grep -q '^>> up:' "$LOG" && break
  kill -0 "$LAUNCHER" 2>/dev/null || { echo "!! launcher died during startup:"; cat "$LOG"; exit 1; }
  sleep 1
done
grep -q '^>> up:' "$LOG" || { echo "!! timeout waiting for instance:"; cat "$LOG"; exit 1; }

DISP="$(sed -n 's/^>> xvfb up on \(:[0-9]\+\).*/\1/p' "$LOG")"
WIN="$(sed -n "s/^>> up:.*window='\([^']*\)'.*/\1/p" "$LOG")"
NODE_LOG="$(sed -n 's/^>> \[node\] pid=[0-9]\+ log=\(.*\)/\1/p' "$LOG")"
echo ">> instance up: display=$DISP window='$WIN'"

# Node up? RunNode.sh logs its base URL; poll /api/server/info until it answers.
NODE_URL=''
for _ in $(seq 1 30); do
  NODE_URL="$(sed -n 's|^>> sentinelflow node.*: \(http://[0-9.:]\+\) .*|\1|p' "$NODE_LOG" 2>/dev/null | tail -1)"
  [[ -n "$NODE_URL" ]] && curl -fsS -m 1 "$NODE_URL/api/server/info" >/dev/null 2>&1 && break
  sleep 1
done
[[ -n "$NODE_URL" ]] || { echo "!! node never came up:"; cat "$NODE_LOG" 2>/dev/null; exit 1; }
echo ">> node answering: $NODE_URL/api/server/info -> $(curl -fsS -m 2 "$NODE_URL/api/server/info")"

# Type into the notepad: focus the desktop window, click its center to land
# the caret in notepad's edit area, then send real XTEST key events — wine
# drops XSendEvent-style input, so this mirrors linux_handler's focus+XTEST.
export DISPLAY="$DISP"
WID="$(xdotool search --name "$WIN" | head -1)"
eval "$(xdotool getwindowgeometry --shell "$WID")"   # fills WIDTH/HEIGHT
xdotool windowfocus --sync "$WID"
xdotool mousemove --window "$WID" $((WIDTH / 2)) $((HEIGHT / 2))
sleep 0.2
xdotool click 1
sleep 0.3
xdotool type --delay 60 "$MSG"
echo ">> typed: '$MSG'"

# Proof: capture the window through the system's own capturer.
.venv/bin/python - "$WIN" "$OUT" <<'PY'
import sys, cv2
from Src.infrastructure.os.linux_handler import LinuxWindowManager, LinuxScreenCapturer
title, out = sys.argv[1], sys.argv[2]
wid = LinuxWindowManager().find_window_by_title(title)
img = LinuxScreenCapturer().capture_window(wid)
cv2.imwrite(out, img)
print(f">> captured {img.shape[1]}x{img.shape[0]} -> {out}")
PY

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
