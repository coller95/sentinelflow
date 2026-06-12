#!/usr/bin/env bash
# launch.sh — bring up wine app instances and SUPERVISE them. Stays in the
# foreground; Ctrl+C (or any exit) tears down EVERYTHING it spawned.
#
# Modes (combinable):
#   default : ONE shared wine virtual desktop, COUNT apps inside it.
#   --xvfb  : the instance gets its OWN headless X server (exact size, no WM).
#             View it through the node's capture API / orchestrator CCTV.
#   --net   : ONE instance with its OWN distinct LAN IP (netns; needs sudo).
#             Wired = DHCP, WiFi = static. Run one per terminal for multibox.
#
# Bootstrap the prefix first:  ./deploy/bootstrap.sh <PREFIX>
#
# Usage:
#   ./deploy/launch.sh -p <PREFIX> [options]
#
# Options:
#   -p, --prefix DIR     WINEPREFIX to run in (required)
#   -n, --name NAME      desktop name (default: basename of PREFIX, dots stripped)
#   -r, --res WxH        virtual-desktop size (default: 1024x768)
#   -a, --app NAME       app to run (default: notepad)
#   -c, --count N        apps in the shared desktop (default: 3; --net forces 1)
#   -w, --workspace N    park the desktop on EWMH workspace N (0-indexed),
#                        or 'new' (alias 'n') for a fresh/trailing workspace
#   -e, --env K=V        extra env var for every app (repeatable)
#   -t, --timeout SEC    seconds to wait for the desktop window (default: 30)
#       --xvfb           run on a fresh per-instance Xvfb display (headless)
#       --node           run a per-instance cluster node (stub by default)
#       --node-cmd CMD   command to run as the node (implies --node);
#                        the real one: --node-cmd Scripts/RunNode.sh
#       --no-node        turn the node back off
#       --own-prefix     run in an OWN per-instance WINEPREFIX under
#                        ~/.local/state/sentinelflow/<name>/wineprefix (wine
#                        initializes it on first boot), so teardown's
#                        'wineserver -k' only stops THIS instance's wine apps
#       --wineprefix DIR put the own prefix at DIR (implies --own-prefix)
#       --net            give the instance its own LAN IP via netns (sudo).
#                        Wired: DHCP. WiFi: static (auto-picked free LAN addr).
#       --parent IFACE   physical iface for --net (default: auto-detect; implies --net)
#       --ip ADDR        force the static IP, WiFi (default auto-pick; implies --net)
#   -h, --help           this help
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/modules/log.sh"
source "$HERE/modules/teardown.sh"
source "$HERE/modules/sudo.sh"
source "$HERE/modules/netns.sh"
source "$HERE/modules/xserver.sh"
source "$HERE/modules/cli.sh"
source "$HERE/modules/preflight.sh"
source "$HERE/modules/desktop.sh"
source "$HERE/modules/apps.sh"
source "$HERE/modules/node.sh"

parse_cli "$@"
preflight
derive_name
resolve_own_prefix   # --own-prefix: repoint PREFIX before the trap goes live —
                     # an early die() must not 'wineserver -k' the shared prefix
install_teardown
start_xserver   # --xvfb: own headless display; exports DISPLAY for all below

# ── --net: give this instance its own LAN IP, then run everything inside the ns ──
if (( NET )); then
  sudo_init
  net_detect_parent
  NS="ns_$NAME"
  IFACE="sf_$NAME"; IFACE="${IFACE:0:15}"   # kernel caps iface names at 15 chars
  net_create "$NS" "$IFACE"
  net_address
  NS_RUN=( sudo ip netns exec "$NS" runuser -u "$USER" -- )
fi

build_run_env

log "bringing up desktop '$NAME' ($RES) with $COUNT x $APP"

run_app 1
wait_for_window

# extra apps only share the desktop in normal mode (--net is a single instance)
if (( ! NET )); then
  for (( n=2; n<=COUNT; n++ )); do run_app "$n"; sleep 0.5; done
fi

park_workspace
start_node

echo ">> up: prefix=$PREFIX name='$NAME' window='$WIN_NAME' wid=$WID apps=$COUNT${LEASE_IP:+ ip=$LEASE_IP}"
echo ">> supervising — Ctrl+C to stop and tear down all."

# Supervise: the FIRST member to die ends the whole instance (wait-all would
# sleep through a dead app while the node lives on, serving stale frames).
# bash < 5.3 'wait -n' ignores pids already dead when called ("no such job",
# then it blocks on the survivors) — so sweep ALL_PIDS for a corpse first and
# re-sweep on every wakeup, only blocking in wait -n while all look alive.
# Liveness probe: kill -0 EPERMs on the root-owned sudo front-ends that --net
# puts in ALL_PIDS, so a still-present /proc entry also counts as alive.
DEAD=""
while [[ -z "$DEAD" ]]; do
  for pid in "${ALL_PIDS[@]}"; do
    kill -0 "$pid" 2>/dev/null || [[ -e "/proc/$pid" ]] || { DEAD="$pid"; break; }
  done
  [[ -n "$DEAD" ]] && break
  REAPED=""
  wait -n -p REAPED "${ALL_PIDS[@]}" 2>/dev/null || true
  (( cleaned )) && exit 0       # a signal already tore us down mid-wait
  DEAD="${REAPED:-}"            # set: wait -n caught the death itself
  [[ -n "$DEAD" ]] || sleep 1   # unset: buggy return — pace the re-sweep
done
echo ">> member pid=$DEAD died — ending instance."
