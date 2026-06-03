#!/usr/bin/env bash
# teardown.sh — own the spawned-process lifecycle + single, idempotent teardown.
# Source me.

ALL_PIDS=()
cleaned=0

cleanup(){
  (( $cleaned )) && return; cleaned=1
  echo; echo ">> tearing down '$NAME' ..."
  (( ${#ALL_PIDS[@]} )) && kill "${ALL_PIDS[@]}" 2>/dev/null || true
  # wineserver -k stops every wine process in THIS prefix; NS_RUN routes it into
  # the network namespace in --net mode (empty array = plain host run otherwise).
  "${NS_RUN[@]}" env WINEPREFIX="$PREFIX" wineserver -k 2>/dev/null || true
  if (( NET )); then
    net_destroy "$NS" "$IFACE"
    sudo_stop   # LAST: keep sudo valid until net_destroy is done
  fi
  echo ">> down."
}

install_teardown(){ trap cleanup INT TERM EXIT; }
