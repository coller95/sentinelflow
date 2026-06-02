#!/usr/bin/env bash
# play.sh — run ONE WC3+MH instance inside a volatile network namespace,
# giving it a distinct LAN IP via ipvlan (WiFi-safe: shares parent MAC).
# Everything (netns, ipvlan iface, per-ns DNS) is created on start and
# DESTROYED on exit — nothing persists across reboot.
#
# Usage:  ./play.sh <PREFIX> <LAN_IP> [NS_NAME]
#   PREFIX  = wine prefix path           (e.g. ~/.wineGame1)
#   LAN_IP  = distinct free LAN IP        (e.g. 192.168.1.150)
#   NS_NAME = namespace name (default: derived from prefix basename)
#
# Example (one per terminal):
#   ./play.sh ~/.wine       192.168.1.150
#   ./play.sh ~/.wineGame1  192.168.1.151
#   ./play.sh ~/.wineGame2  192.168.1.152
set -u

FS=0
if [[ "${1:-}" == "--fullscreen" || "${1:-}" == "-f" ]]; then FS=1; shift; fi

PREFIX="${1:?need PREFIX}"; LAN_IP="${2:?need LAN_IP}"
NS="${3:-ns_$(basename "$PREFIX")}"
IPV="ipv_$(basename "$PREFIX")"   # ipvlan iface name (<=15 chars)

# ── LAN config (auto-detected defaults; override by editing) ──
PARENT="wlo1"            # physical iface (WiFi). check: ip route get 1.1.1.1
GATEWAY="192.168.1.1"
CIDR="24"
DNS="192.168.1.1"       # per-ns resolver; 1.1.1.1 also fine
HERE="$(cd "$(dirname "$0")" && pwd)"

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

echo ">> [$NS] launch game as $USER, IP $LAN_IP"
# drop root back to your user; keep X + HOME so wine/vision work
sudo ip netns exec "$NS" runuser -u "$USER" -- \
  env DISPLAY="${DISPLAY:-:0}" XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}" \
      HOME="$HOME" WINEPREFIX="$PREFIX" FULLSCREEN="$FS" WORKSPACE="${WORKSPACE:-}" \
  "$HERE/wc3.sh" "$PREFIX"
# wc3.sh blocks; Ctrl+C reaches it (kills wine) then EXIT trap tears down netns
