#!/usr/bin/env bash
# preflight.sh — dependency + prefix validation. Source me.

preflight(){
  [[ -n "$PREFIX" ]] || die "need --prefix (see --help)"
  [[ -d "$PREFIX" ]] || die "prefix not found: $PREFIX (run ./deploy/bootstrap.sh $PREFIX first)"
  command -v wine    >/dev/null || die "wine not on PATH"
  command -v xdotool >/dev/null || die "xdotool not on PATH"
}
