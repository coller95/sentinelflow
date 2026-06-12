#!/usr/bin/env bash
# preflight.sh — dependency + prefix validation. Source me.

preflight(){
  [[ -n "$PREFIX" ]] || die "need --prefix (see --help)"
  [[ -d "$PREFIX" ]] || die "prefix not found: $PREFIX (run ./deploy/bootstrap.sh $PREFIX first)"
  command -v wine    >/dev/null || die "wine not on PATH"
  command -v xdotool >/dev/null || die "xdotool not on PATH"
  if (( XVFB )); then
    command -v Xvfb >/dev/null || die "Xvfb not on PATH (needed for --xvfb; apt install xvfb)"
  fi
  if (( NET )); then
    command -v ip >/dev/null || die "ip (iproute2) not on PATH (needed for --net)"
    # --net is a single instance. Force COUNT=1; only object if the user asked
    # for something else explicitly (run multiple terminals for multibox).
    if (( COUNT_SET )); then
      (( COUNT == 1 )) || die "--net runs ONE instance per call; drop -c or use --count 1, run multiple terminals for multibox"
    else
      COUNT=1
    fi
  fi
}

# resolve_own_prefix — --own-prefix: point PREFIX at this instance's own dir.
# Every later consumer follows for free (run_app's WINEPREFIX, the node's
# SF_PREFIX, teardown's 'wineserver -k'), so stopping one instance can no
# longer kill wine apps of other launches sharing the bootstrapped prefix.
# Called from launch.sh AFTER derive_name (the default location needs $NAME,
# which derive_name fills only after preflight runs) and BEFORE install_teardown:
# the trap is live the moment it is installed, so a die() before the repoint
# (Xvfb failure, aborted --net setup) would hand teardown's 'wineserver -k' the
# shared -p prefix — the exact cross-kill this flag exists to prevent. wine
# initializes a missing prefix by itself on first boot; only the parent dir has
# to exist.
resolve_own_prefix(){
  (( OWN_PREFIX )) || return 0
  OWN_PREFIX_DIR="${OWN_PREFIX_DIR:-$HOME/.local/state/sentinelflow/$NAME/wineprefix}"
  # a relative --wineprefix DIR would silently create the prefix under whatever
  # cwd launch.sh was invoked from — pin it to an absolute path once, here.
  OWN_PREFIX_DIR="$(realpath -m -- "$OWN_PREFIX_DIR")"
  if [[ ! -d "$OWN_PREFIX_DIR" ]]; then
    log "own prefix $OWN_PREFIX_DIR not initialized — first boot runs wineboot (takes a few seconds)"
    mkdir -p "$(dirname "$OWN_PREFIX_DIR")"
  fi
  PREFIX="$OWN_PREFIX_DIR"
}
