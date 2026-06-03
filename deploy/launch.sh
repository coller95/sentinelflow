#!/usr/bin/env bash
# launch.sh — bring up wine app instances and SUPERVISE them. Stays in the
# foreground; Ctrl+C (or any exit) tears down EVERYTHING it spawned.
#
# Two modes:
#   default : ONE shared wine virtual desktop, COUNT apps inside it.
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
#   -w, --workspace N    park the desktop on EWMH workspace N (0-indexed)
#   -e, --env K=V        extra env var for every app (repeatable)
#   -t, --timeout SEC    seconds to wait for the desktop window (default: 30)
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
source "$HERE/modules/cli.sh"
source "$HERE/modules/preflight.sh"
source "$HERE/modules/desktop.sh"
source "$HERE/modules/apps.sh"

parse_cli "$@"
preflight
derive_name
install_teardown

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

echo ">> up: prefix=$PREFIX name='$NAME' window='$WIN_NAME' wid=$WID apps=$COUNT${LEASE_IP:+ ip=$LEASE_IP}"
echo ">> supervising — Ctrl+C to stop and tear down all."

wait "${ALL_PIDS[@]}"
