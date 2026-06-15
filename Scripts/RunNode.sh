#!/usr/bin/env bash
# RunNode.sh — run ONE SentinelFlow cluster server as a wine-deploy node.
#
# Built to ride deploy/launch.sh --node-cmd. Consumes SF_NAME, SF_RES, SF_IP
# from the deploy SF_* env (the rest — SF_PREFIX SF_WID SF_DISPLAY — is
# available to payloads but unused here; DISPLAY itself is inherited) and
# isolates everything per instance:
#   state -> ~/.local/state/sentinelflow/<name>/state.json (own serverUuid)
#   port  -> $SENTINELFLOW_PORT if set; else 8000 when the instance has its own
#            IP (--net); else the first free port in 8001-8099 on the shared
#            host, reserved via flock so concurrent launches can't collide
#   attach-> first boot seeds defaultWindowTitle "<name> - Wine Desktop" so the
#            server auto-attaches to THIS instance's wine desktop window
#
# Standalone run (no deploy) also works: defaults to NAME=local.
# Optional: SF_ORCH_URL=http://host:8010 auto-commissions this node into a
# running orchestrator once the server answers.
#
# Usage:
#   ./deploy/launch.sh -p ~/.wineGame1 -c 1 --xvfb --node-cmd Scripts/RunNode.sh
set -euo pipefail

SCRIPTDIR="$(cd -- "$(dirname "$0")" >/dev/null; pwd -P)"
PROJECT_ROOT="$(dirname "$SCRIPTDIR")"
cd "$PROJECT_ROOT"

NAME="${SF_NAME:-local}"
RES="${SF_RES:-1024x768}"
# NAME lands in JSON, file paths and window-title regexes; RES in JSON + Xvfb.
# Validate once here instead of escaping in every consumer.
[[ "$NAME" =~ ^[A-Za-z0-9._-]+$ ]] || { echo "ERR: bad instance name '$NAME' (use letters/digits/._-)" >&2; exit 1; }
[[ "$RES"  =~ ^[0-9]+x[0-9]+$    ]] || { echo "ERR: bad RES '$RES' (want WxH, e.g. 1024x768)" >&2; exit 1; }

STATE_DIR="${SENTINELFLOW_STATE_DIR:-$HOME/.local/state/sentinelflow/$NAME}"
mkdir -p "$STATE_DIR"

# One node per instance: hold the state dir for our whole lifetime (fd 8
# survives the exec below, so the lock lives as long as the server).
exec 8>"$STATE_DIR/.lock"
flock -n 8 || { echo "ERR: node for '$NAME' already running ($STATE_DIR locked)" >&2; exit 1; }

# Port: explicit > own-IP instance (8000 is free inside its netns) > probe the
# shared host. The probe BINDS 0.0.0.0 (what the server will do — a connect
# test misses LAN-only listeners) and takes a per-port flock kept until we die
# (fd 9 survives exec), so two nodes starting together can't pick the same port.
PORT=""
if [[ -n "${SENTINELFLOW_PORT:-}" ]]; then
  PORT="$SENTINELFLOW_PORT"
elif [[ -n "${SF_IP:-}" ]]; then
  PORT=8000
else
  for p in $(seq 8001 8099); do
    exec 9>"${TMPDIR:-/tmp}/sf-port-$p.lock"
    if flock -n 9 && "$PROJECT_ROOT/.venv/bin/python" -c "
import socket
s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(('0.0.0.0', $p))
s.close()" 2>/dev/null; then
      PORT="$p"; break
    fi
    exec 9>&-
  done
  [[ -n "$PORT" ]] || { echo "ERR: no free port in 8001-8099" >&2; exit 1; }
fi

# First boot of this instance: seed state so the server auto-attaches to OUR
# wine desktop window. Existing state is kept verbatim — serverUuid must stay
# stable across relaunches or the orchestrator sees a brand-new node every run.
# The uuid is seeded here because the server only persists state on mutating
# API calls — a fresh boot that never gets one would re-roll its identity.
if [[ ! -f "$STATE_DIR/state.json" ]]; then
  W="${RES%x*}"; H="${RES#*x}"
  UUID="$(cat /proc/sys/kernel/random/uuid)"
  # --no-desktop instances pass the game's own window title via SF_WIN_TITLE;
  # default to the wine virtual-desktop title.
  TITLE="${SF_WIN_TITLE:-$NAME - Wine Desktop}"
  cat > "$STATE_DIR/state.json" <<EOF
{
  "version": 1,
  "serverUuid": "$UUID",
  "app": {
    "defaultAppPath": "",
    "defaultWindowTitle": "$TITLE",
    "defaultWindowLeft": 0,
    "defaultWindowTop": 0,
    "defaultWindowWidth": $W,
    "defaultWindowHeight": $H
  }
}
EOF
fi

BASE_URL="http://${SF_IP:-127.0.0.1}:$PORT"
echo ">> sentinelflow node '$NAME': $BASE_URL  state=$STATE_DIR"

# Auto-commission into the orchestrator once our API answers. Background, best
# effort: the node is fully usable without an orchestrator.
if [[ -n "${SF_ORCH_URL:-}" ]]; then
  (
    for _ in $(seq 1 30); do
      sleep 1
      curl -fsS -m 2 "$BASE_URL/api/server/info" >/dev/null 2>&1 || continue
      curl -fsS -m 5 -X POST "$SF_ORCH_URL/api/orchestrator/clusters/commission_from_url" \
        -H 'Content-Type: application/json' \
        -d "{\"baseUrl\":\"$BASE_URL\",\"label\":\"$NAME\"}" >/dev/null \
        && { echo ">> commissioned '$NAME' into $SF_ORCH_URL"; exit 0; }
    done
    echo ">> WARN: could not commission '$NAME' into $SF_ORCH_URL" >&2
  ) &
fi

export SENTINELFLOW_STATE_DIR="$STATE_DIR" SENTINELFLOW_PORT="$PORT"
exec "$PROJECT_ROOT/.venv/bin/python" -m Src.cluster.main
