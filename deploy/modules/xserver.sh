#!/usr/bin/env bash
# xserver.sh — optional per-instance Xvfb (--xvfb). Source me.
#
# Gives the instance its OWN headless X server sized exactly to $RES: no WM, no
# compositor, no other windows. This is the environment the node's capture and
# input paths are written for (see Src/infrastructure/os/linux_handler.py) —
# per-window XGetImage is exact and focus-free, clicks can't fight a real
# pointer, and the wine desktop can't be resized/fullscreened by a desktop WM.
# View a headless instance through the node's capture API / orchestrator CCTV.

XVFB=0           # set by cli (--xvfb)
XVFB_DISPLAY=""  # ":N" picked in start_xserver

# start_xserver — boot Xvfb and point $DISPLAY at it. Xvfb picks its own free
# display number (-displayfd): probing lock/socket files ourselves is a TOCTOU
# race when two launches start together — both can adopt the same display.
# Everything launched after this (wine, xdotool, node) inherits the display.
start_xserver(){
  (( XVFB )) || return 0
  local xlog="${TMPDIR:-/tmp}/xvfb-${NAME}.log"
  echo "── run $(date '+%F %T') ──" >>"$xlog"

  local dfile pid n="" i
  dfile="$(mktemp "${TMPDIR:-/tmp}/xvfb-${NAME}-XXXXXX.display")"
  Xvfb -displayfd 6 -screen 0 "${RES}x24" -nolisten tcp 6>"$dfile" >>"$xlog" 2>&1 &
  pid=$!
  for i in $(seq 1 100); do
    n="$(tr -d '[:space:]' <"$dfile" 2>/dev/null)"
    [[ -n "$n" ]] && break
    kill -0 "$pid" 2>/dev/null || break
    sleep 0.1
  done
  rm -f "$dfile"
  if [[ -z "$n" ]]; then
    kill "$pid" 2>/dev/null || true
    die "Xvfb failed to start (see $xlog)"
  fi

  ALL_PIDS+=("$pid")
  XVFB_DISPLAY=":$n"
  export DISPLAY="$XVFB_DISPLAY"
  unset XAUTHORITY   # Xvfb runs without auth; a stale host cookie would break clients
  log "xvfb up on $DISPLAY (${RES}, pid=$pid)"
}
