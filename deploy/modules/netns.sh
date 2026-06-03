#!/usr/bin/env bash
# netns.sh — give one instance its own distinct LAN IP in a volatile network
# namespace. Everything is created on start and destroyed on teardown — nothing
# persists. Source me.
#
# Link type + addressing depend on the parent:
#   Wired -> macvlan (own MAC). DHCP works: the kernel demuxes inbound frames by
#            MAC, so the per-instance OFFER reaches the namespace.
#   WiFi  -> ipvlan l2 (shares parent MAC; APs drop the foreign MAC a macvlan
#            would use). DHCP CANNOT work here: ipvlan demuxes inbound packets by
#            destination IP, but DHCP must run before an IP exists, so the OFFER
#            never reaches the namespace. We assign a STATIC IP instead (a free
#            address probed in the host's LAN subnet), which the by-IP demux then
#            delivers correctly.

NET=0            # set by cli (--net)
PARENT=""        # physical iface (auto-detected when empty)
IP_REQ=""        # caller-forced static IP (--ip); empty = auto-pick (ipvlan)
NS=""            # namespace name
IFACE=""         # macvlan/ipvlan iface name (kernel caps at 15 chars)
LINK_KIND=""     # macvlan | ipvlan (decided in net_create)
DHCP_CLIENT=""   # dhclient | udhcpc
LEASE_IP=""      # address this instance ended up with (DHCP lease or static)
NS_RUN=()        # command prefix to run things inside the ns (empty when !NET)

net_detect_parent(){
  [[ -n "$PARENT" ]] && return
  PARENT="$(ip route get 1.1.1.1 2>/dev/null | sed -n 's/.* dev \([^ ]*\).*/\1/p' | head -1)"
  [[ -n "$PARENT" ]] || die "could not auto-detect parent iface (pass --parent)"
}

net_is_wireless(){ [[ -d "/sys/class/net/$1/wireless" ]]; }

net_pick_dhcp(){
  if   command -v dhclient >/dev/null; then DHCP_CLIENT=dhclient
  elif command -v udhcpc   >/dev/null; then DHCP_CLIENT=udhcpc
  else die "no DHCP client found (install isc-dhcp-client or busybox udhcpc)"; fi
}

# net_create $ns $iface — build the volatile ns + link, bring it up
net_create(){
  NS="$1"; IFACE="$2"
  if net_is_wireless "$PARENT"; then LINK_KIND=ipvlan; else LINK_KIND=macvlan; fi
  log "netns $NS: $LINK_KIND '$IFACE' on $PARENT"
  sudo ip netns add "$NS"
  if [[ "$LINK_KIND" == ipvlan ]]; then
    sudo ip link add "$IFACE" link "$PARENT" type ipvlan mode l2
  else
    sudo ip link add "$IFACE" link "$PARENT" type macvlan mode bridge
  fi
  sudo ip link set "$IFACE" netns "$NS"
  sudo ip netns exec "$NS" ip link set lo up
  sudo ip netns exec "$NS" ip link set "$IFACE" up
  # pre-create per-ns resolv.conf so our DNS lands here (ip netns exec bind-mounts
  # /etc/netns/$NS over /etc) and NOT on the host's real resolv.conf
  sudo mkdir -p "/etc/netns/$NS"
  sudo touch    "/etc/netns/$NS/resolv.conf"
}

# net_address — give IFACE an address inside NS; sets LEASE_IP.
# macvlan -> DHCP; ipvlan -> static (DHCP can't bootstrap on ipvlan, see header).
net_address(){
  if [[ "$LINK_KIND" == macvlan ]]; then net_dhcp; else net_static; fi
}

# net_dhcp — lease an address on IFACE inside NS (macvlan path)
net_dhcp(){
  net_pick_dhcp
  log "netns $NS: DHCP via $DHCP_CLIENT on $IFACE"
  if [[ "$DHCP_CLIENT" == dhclient ]]; then
    local cf="/tmp/dhclient-$NS.conf"
    printf 'send dhcp-client-identifier "sf-%s";\ntimeout 20;\n' "$NS" | sudo tee "$cf" >/dev/null
    sudo ip netns exec "$NS" dhclient -1 -cf "$cf" "$IFACE" || die "DHCP failed in $NS"
  else
    sudo ip netns exec "$NS" udhcpc -i "$IFACE" -n -q -t 5 -x "hostname:sf-$NS" || die "DHCP failed in $NS"
  fi
  LEASE_IP="$(sudo ip netns exec "$NS" ip -4 -o addr show "$IFACE" 2>/dev/null | sed -n 's/.* inet \([0-9.]*\).*/\1/p' | head -1)"
  [[ -n "$LEASE_IP" ]] || die "no DHCP lease on $IFACE in $NS"
  log "netns $NS: leased $LEASE_IP"
}

# net_try_assign $ip $cidr — try to claim $ip on IFACE inside NS. Returns
# non-zero (quietly) if the kernel rejects it, e.g. another ipvlan slave on the
# same parent already holds it ("Address already assigned to an ipvlan device").
# That check spans EVERY slave of the parent across ALL namespaces, so a leftover
# instance's address counts as taken even though it never answers a ping.
net_try_assign(){
  sudo ip netns exec "$NS" ip addr add "$1/$2" dev "$IFACE" 2>/dev/null
}

# net_static — assign a static IP + route + DNS inside NS (ipvlan path).
#   --ip ADDR : one shot, hard fail on any collision.
#   auto      : walk $net.200-.250, take the first the kernel actually accepts.
net_static(){
  local gw cidr net ip h
  gw="$(ip route | sed -n 's/^default via \([0-9.]*\) dev '"$PARENT"'.*/\1/p' | head -1)"
  [[ -n "$gw" ]] || gw="$(ip route | sed -n 's/^default via \([0-9.]*\).*/\1/p' | head -1)"
  cidr="$(ip -4 -o addr show "$PARENT" | sed -n 's/.* inet [0-9.]*\/\([0-9]*\) .*/\1/p' | head -1)"
  [[ -n "$gw" && -n "$cidr" ]] || die "could not derive gateway/subnet from $PARENT (pass --ip)"
  net="${gw%.*}"   # /24 base from the gateway (good enough for home LANs)

  if [[ -n "$IP_REQ" ]]; then
    ip="$IP_REQ"
    # forced address: probe from the host before claiming it, so we fail loud on
    # a collision instead of silently fighting another host for the same IP.
    ! ping -c1 -W1 "$ip" >/dev/null 2>&1 || die "requested IP $ip already in use on the LAN (pick another --ip)"
    log "netns $NS: static $ip/$cidr gw $gw on $IFACE"
    net_try_assign "$ip" "$cidr" || die "could not assign $ip in $NS (held by another instance? pick another --ip)"
  else
    # ping alone is unreliable (WiFi hosts ignore it; sibling ipvlan slaves never
    # answer), so let the kernel be the judge: skip anything that pings back, then
    # actually attempt the add and step to the next host if it's refused.
    ip=""
    for h in $(seq 200 250); do
      ping -c1 -W1 "$net.$h" >/dev/null 2>&1 && continue
      if net_try_assign "$net.$h" "$cidr"; then ip="$net.$h"; break; fi
    done
    [[ -n "$ip" ]] || die "no free address found in $net.200-.250 (pass --ip)"
    log "netns $NS: static $ip/$cidr gw $gw on $IFACE"
  fi

  sudo ip netns exec "$NS" ip route add default via "$gw"
  # DNS: use the gateway as resolver. The host's 127.0.0.53 systemd-resolved stub
  # is UNREACHABLE inside a netns, so copying /etc/resolv.conf would break DNS.
  echo "nameserver $gw" | sudo tee "/etc/netns/$NS/resolv.conf" >/dev/null

  sudo ip netns exec "$NS" ping -c1 -W2 "$gw" >/dev/null 2>&1 \
    || die "static $ip set but gateway $gw unreachable in $NS (address in use? try --ip)"
  LEASE_IP="$ip"
  log "netns $NS: up at $LEASE_IP"
}

# net_destroy $ns $iface — tolerant teardown (safe to call with empty ns)
net_destroy(){
  local ns="$1" iface="${2:-}"
  [[ -n "$ns" ]] || return 0
  [[ "$LINK_KIND" == macvlan ]] && \
    sudo ip netns exec "$ns" "${DHCP_CLIENT:-dhclient}" -r "$iface" 2>/dev/null || true
  sudo ip netns del "$ns" 2>/dev/null || true
  sudo rm -rf "/etc/netns/$ns" 2>/dev/null || true
  sudo rm -f  "/tmp/dhclient-$ns.conf" 2>/dev/null || true
}
