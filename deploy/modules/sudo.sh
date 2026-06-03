#!/usr/bin/env bash
# sudo.sh — one-time sudo auth + keep-alive for the whole run. Source me.
# --net needs root for netns/ipvlan setup AND teardown (which can happen hours
# later). Prompt once up front, then refresh the sudo timestamp in the
# background so teardown never re-prompts or fails on an expired session.

SUDO_KEEPALIVE_PID=""

sudo_init(){
  [[ $EUID -eq 0 ]] && die "run as your user, not root (sudo is handled per-step)"
  command -v sudo >/dev/null || die "sudo not on PATH (needed for --net)"
  log "need sudo for netns setup/teardown (one prompt)"
  sudo -v || die "sudo authentication failed"
  # refresh every 50s (default timestamp_timeout is ~15min); exit if it lapses
  ( while true; do sudo -n -v 2>/dev/null || exit; sleep 50; done ) &
  SUDO_KEEPALIVE_PID=$!
}

sudo_stop(){
  [[ -n "${SUDO_KEEPALIVE_PID:-}" ]] && kill "$SUDO_KEEPALIVE_PID" 2>/dev/null || true
  SUDO_KEEPALIVE_PID=""
}
