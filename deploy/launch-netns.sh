#!/usr/bin/env bash
# launch-netns.sh — run ONE app instance inside a volatile network namespace,
# giving it a distinct LAN IP via ipvlan (WiFi-safe: shares parent MAC).
# Generic, app-agnostic wrapper (was play.sh): the APP is selected by a
# PROFILE bash file handed to launch.sh. Everything (netns, ipvlan iface,
# per-ns DNS) is created on start and DESTROYED on exit — nothing persists.
#
# Usage:  ./launch-netns.sh [--fullscreen|-f] [--workspace|-w N] <PROFILE> <PREFIX> <LAN_IP> [NS_NAME]
#   PROFILE       = app profile bash file (e.g. apps/wc3/config.sh)
#   PREFIX        = wine prefix path      (e.g. ~/.wineGame1)
#   LAN_IP        = distinct free LAN IP  (e.g. 192.168.1.150)
#   NS_NAME       = namespace name (default: derived from prefix basename)
#   --fullscreen  = pass through to launch.sh (APP_MAIN native, no wine desktop)
#   --workspace N = park this instance on GNOME/EWMH workspace N (env WORKSPACE also works)
#
# Example (one per terminal, distinct LAN IPs + workspaces):
#   ./launch-netns.sh -w 0 apps/wc3/config.sh ~/.wine       192.168.1.150
#   ./launch-netns.sh -w 1 apps/wc3/config.sh ~/.wineGame1  192.168.1.151
#   ./launch-netns.sh -w 2 apps/wc3/config.sh ~/.wineGame2  192.168.1.152
set -u

# flags (before positionals); WORKSPACE env is the fallback for -w
FS=0
WS="${WORKSPACE:-}"
while :; do case "${1:-}" in
  --fullscreen|-f) FS=1; shift ;;
  --workspace|-w)  WS="${2:-}"; shift 2 ;;
  --) shift; break ;;
  -*) echo "ERR: unknown flag '$1'" >&2; exit 2 ;;
  *) break ;;
esac; done

PROFILE="${1:?need PROFILE}"; PREFIX="${2:?need PREFIX}"; LAN_IP="${3:?need LAN_IP}"
NS="${4:-ns_$(basename "$PREFIX")}"
IPV="ipv_$(basename "$PREFIX")"   # ipvlan iface name (<=15 chars)

HERE="$(cd "$(dirname "$0")" && pwd)"
# Resolve PROFILE to an ABSOLUTE path NOW — CWD/relative won't resolve once
# we're inside the netns (runuser -u runs with a possibly different CWD).
if [[ "$PROFILE" != /* ]]; then PROFILE="$HERE/$PROFILE"; fi
PROFILE="$(cd "$(dirname "$PROFILE")" && pwd)/$(basename "$PROFILE")"
[[ -f "$PROFILE" ]] || { echo "ERR: profile not found: $PROFILE"; exit 1; }

# ── LAN config (auto-detected defaults; override by editing) ──
PARENT="wlo1"            # physical iface (WiFi). check: ip route get 1.1.1.1
GATEWAY="192.168.1.1"
CIDR="24"
DNS="192.168.1.1"       # per-ns resolver; 1.1.1.1 also fine

[[ $EUID -eq 0 ]] && { echo "run as your user, not root (script sudo's itself)"; exit 1; }

teardown(){
  echo; echo ">> teardown $NS (volatile)"
  sudo ip netns del "$NS" 2>/dev/null          # also removes the ipvlan iface inside it
  sudo rm -rf "/etc/netns/$NS" 2>/dev/null
}
trap teardown INT TERM EXIT

# ── build volatile netns + ipvlan ──
if ! ip netns list | grep -qw "$NS"; then
  echo ">> create netns $NS + ipvlan $IPV ($LAN_IP) on $PARENT"
  sudo ip netns add "$NS"
  sudo ip link add "$IPV" link "$PARENT" type ipvlan mode l2
  sudo ip link set "$IPV" netns "$NS"
  sudo ip netns exec "$NS" ip link set lo up
  sudo ip netns exec "$NS" ip link set "$IPV" up
  sudo ip netns exec "$NS" ip addr add "$LAN_IP/$CIDR" dev "$IPV"
  sudo ip netns exec "$NS" ip route add default via "$GATEWAY"
  # per-ns DNS (root-ns 127.0.0.53 stub is unreachable inside a netns)
  sudo mkdir -p "/etc/netns/$NS"
  echo "nameserver $DNS" | sudo tee "/etc/netns/$NS/resolv.conf" >/dev/null
else
  echo ">> netns $NS already exists, reusing"
fi

echo ">> [$NS] launch app as $USER, IP $LAN_IP, profile $(basename "$PROFILE")"
# drop root back to your user; keep X + HOME so wine/vision work
sudo ip netns exec "$NS" runuser -u "$USER" -- \
  env DISPLAY="${DISPLAY:-:0}" XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}" \
      HOME="$HOME" WINEPREFIX="$PREFIX" FULLSCREEN="$FS" WORKSPACE="$WS" \
  "$HERE/launch.sh" "$PROFILE" "$PREFIX"
# launch.sh blocks; Ctrl+C reaches it (kills wine) then EXIT trap tears down netns
