#!/usr/bin/env bash
# profiles.sh — app launch profiles. Source me.
#
# Decouples per-app launch knobs from the core script: `-a <name>` loads
# deploy/apps/<name>.app (a sourced KEY=VAL file) which sets the launch globals
# (APP exe path, APP_ARGS, NO_DESKTOP, WIN_TITLE, HOLD_PROC, PROFILE_COUNT).
# A new app = drop a new deploy/apps/<name>.app; the core never changes. Any -a
# value that is not a bare profile name (a real wine path, or an unknown name)
# passes through unchanged.

PROFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." >/dev/null && pwd)/apps"

# resolve_app_profile — if $APP names a deploy/apps/<APP>.app profile, load it.
# Called from launch.sh right after parse_cli, before preflight/derive_name.
resolve_app_profile(){
  # Only a bare token can be a profile name; a wine path (C:\…, /foo) passes
  # through, and the regex also blocks any '/' or '..' path traversal.
  [[ "$APP" =~ ^[A-Za-z0-9._-]+$ ]] || return 0
  local f="$PROFILES_DIR/$APP.app"
  [[ -f "$f" ]] || return 0
  PROFILE_COUNT=""
  # shellcheck disable=SC1090
  source "$f"
  # PROFILE_COUNT is the app's default instance count; an explicit -c wins.
  if [[ -n "$PROFILE_COUNT" ]] && (( ! COUNT_SET )); then COUNT="$PROFILE_COUNT"; fi
  return 0
}
