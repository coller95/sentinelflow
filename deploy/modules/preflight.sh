#!/usr/bin/env bash
# preflight.sh — dependency + prefix validation. Source me.

preflight(){
  [[ -n "$PREFIX" ]] || die "need --prefix (see --help)"
  [[ -d "$PREFIX" ]] || die "prefix not found: $PREFIX (run ./deploy/bootstrap.sh $PREFIX first)"
  command -v wine    >/dev/null || die "wine not on PATH"
  command -v xdotool >/dev/null || die "xdotool not on PATH"
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
