#!/usr/bin/env bash
# teardown.sh — spawned-process lifecycle and single teardown. Source me.

ALL_PIDS=()
cleaned=0

cleanup(){
  (($cleaned)) && return; cleaned=1
  echo; echo ">> tearing down '$NAME' ..."
  ((${#ALL_PIDS[@]})) && kill "${ALL_PIDS[@]}" 2>/dev/null || true
  WINEPREFIX="$PREFIX" wineserver -k 2>/dev/null || true
  echo ">> down."
}

install_teardown(){
  trap cleanup INT TERM EXIT
}
