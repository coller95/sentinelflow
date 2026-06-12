#!/usr/bin/env bash
# teardown.sh — own the spawned-process lifecycle + single, idempotent teardown.
# Source me.

ALL_PIDS=()
cleaned=0

cleanup(){
  (( $cleaned )) && return; cleaned=1
  echo; echo ">> tearing down '$NAME' ..."
  # --net members were spawned through NS_RUN, so ALL_PIDS holds the ROOT-owned
  # 'sudo … runuser' front-ends — a plain user kill EPERMs on those. Route the
  # signal through sudo there (keep-alive in sudo.sh means no re-prompt; -n never
  # blocks if it lapsed anyway): sudo relays the TERM to runuser, and runuser
  # forwards it to its payload (TERM, then KILL by itself after a grace period).
  # Anything that still survives inside the ns is swept by net_destroy below.
  if (( NET )); then
    (( ${#ALL_PIDS[@]} )) && sudo -n kill "${ALL_PIDS[@]}" 2>/dev/null || true
  else
    (( ${#ALL_PIDS[@]} )) && kill "${ALL_PIDS[@]}" 2>/dev/null || true
  fi
  # wineserver -k stops every wine process in THIS prefix. In --net mode it must
  # run inside the namespace, but NOT via NS_RUN: that sudo front-end has no -n,
  # so a lapsed session would hang cleanup on a tty password prompt (2>/dev/null
  # cannot silence it) BEFORE net_destroy runs, pinning the ns and its address.
  # Rebuild the prefix with -n so an expired session degrades to a no-op like
  # every other teardown sudo.
  if (( NET )); then
    sudo -n ip netns exec "$NS" runuser -u "$USER" -- env WINEPREFIX="$PREFIX" wineserver -k 2>/dev/null || true
  else
    env WINEPREFIX="$PREFIX" wineserver -k 2>/dev/null || true
  fi
  if (( NET )); then
    net_destroy "$NS" "$IFACE"
    sudo_stop   # LAST: keep sudo valid until net_destroy is done
  fi
  echo ">> down."
}

install_teardown(){ trap cleanup INT TERM EXIT; }
