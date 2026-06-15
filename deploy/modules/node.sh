#!/usr/bin/env bash
# node.sh — per-instance cluster node. Source me.
#
# Every launched instance can carry a NODE: the process that will (later) capture
# and control THIS instance. With no --node-cmd it runs the inline stub below —
# no automation logic, it just proves the wiring. The node starts once the
# desktop window is up, inherits the instance identity via SF_* env, joins
# ALL_PIDS so the launcher supervises and tears it down, and (in --net mode) runs
# inside the instance's netns via NS_RUN so a real node binds the instance's IP.
#
# SF_* handed to the command: SF_NAME SF_PREFIX SF_WID SF_RES SF_DISPLAY SF_WIN_TITLE
# SF_IP (empty unless --net). DISPLAY/XAUTHORITY/HOME are passed for X access;
# SF_ORCH_URL/SENTINELFLOW_PORT ride along when set (RunNode.sh knobs).

# Default payload: print the instance identity, then heartbeat until killed.
_node_stub='echo ">> node-stub up: name=$SF_NAME wid=$SF_WID prefix=$SF_PREFIX display=$SF_DISPLAY res=$SF_RES ip=${SF_IP:-none}"
trap "exit 0" INT TERM
i=0; while :; do i=$((i+1)); echo ">> [node $SF_NAME] heartbeat #$i $(date +%H:%M:%S)"; sleep 5 & wait $!; done'

start_node(){
  (( NODE )) || return 0
  local cmd="${NODE_CMD:-$_node_stub}"
  local log="${TMPDIR:-/tmp}/node-${NAME}.log"
  local -a nenv=(
    "SF_NAME=$NAME" "SF_PREFIX=$PREFIX" "SF_WID=${WID:-}" "SF_RES=$RES"
    "SF_IP=${LEASE_IP:-}" "SF_DISPLAY=${DISPLAY:-:0}" "SF_WIN_TITLE=${WIN_TITLE:-}"
    "DISPLAY=${DISPLAY:-:0}" "XAUTHORITY=${XAUTHORITY:-$HOME/.Xauthority}" "HOME=$HOME"
  )
  # --net runs the node via 'runuser', which scrubs the environment — carry the
  # orchestrator knobs across explicitly, but only when non-empty: a blanket
  # "VAR=${VAR:-}" would hand payloads a set-but-empty var where they had none.
  [[ -n "${SF_ORCH_URL:-}" ]] && nenv+=( "SF_ORCH_URL=$SF_ORCH_URL" )
  [[ -n "${SENTINELFLOW_PORT:-}" ]] && nenv+=( "SENTINELFLOW_PORT=$SENTINELFLOW_PORT" )
  log "node up for '$NAME' (log=$log)"
  echo "── run $(date '+%F %T') ──" >>"$log"
  "${NS_RUN[@]}" env "${nenv[@]}" bash -c "$cmd" >>"$log" 2>&1 &
  ALL_PIDS+=("$!")
  echo ">> [node] pid=$! log=$log"
}
