#!/usr/bin/env bash
# desktop.sh — desktop naming + window lifecycle. Source me.

derive_name(){
  NAME="${NAME:-$(basename "$PREFIX")}"
  NAME="${NAME#"${NAME%%[!.]*}"}"  # strip leading dots (~/.wineTest -> wineTest)
  WIN_NAME="$NAME - Wine Desktop"
}

# wine maps TWO X windows with the SAME title: a wine-internal child (no WM_STATE,
# no _NET_WM_DESKTOP) and the WM-managed top-level that actually sits on a workspace.
# `search | head -1` can return the child, and set_desktop_for_window on it is a
# silent no-op — which broke --workspace. Pick the managed one: it is the match
# that carries a numeric _NET_WM_DESKTOP.
managed_wid(){
  local w d
  for w in $(xdotool search --name "^${WIN_NAME}$" 2>/dev/null); do
    d="$(xdotool get_desktop_for_window "$w" 2>/dev/null || true)"
    [[ "$d" =~ ^[0-9]+$ ]] && { printf '%s\n' "$w"; return 0; }
  done
  return 1
}

wait_for_window(){
  echo ">> waiting for window: '$WIN_NAME' (<=${TIMEOUT}s)"
  WID=""
  for ((i=0; i<TIMEOUT*2; i++)); do
    WID="$(managed_wid || true)"
    [[ -n "$WID" ]] && break
    sleep 0.5
  done
  # No EWMH-managed match (e.g. a WM without virtual desktops): fall back to any
  # match so liveness still resolves — parking is a no-op on such WMs anyway.
  [[ -n "$WID" ]] || WID="$(xdotool search --name "^${WIN_NAME}$" 2>/dev/null | head -1 || true)"
  [[ -n "$WID" ]] || die "desktop window '$WIN_NAME' did not appear in ${TIMEOUT}s"
  echo ">> desktop window id: $WID"
}

# Map $WORKSPACE to a real, in-range desktop index and print it.
#   N      -> N, but if N is out of range try to grow the desktop count (static
#            WMs obey; GNOME's dynamic workspaces ignore it) then clamp + warn.
#   new|n  -> a fresh trailing workspace: grow by one where allowed; on GNOME the
#            dynamic last desktop is already the empty one, so target the last index.
# Returns non-zero (and warns) on an unparseable value so the caller skips parking.
resolve_workspace_target(){
  local n; n="$(xdotool get_num_desktops 2>/dev/null || echo 0)"
  case "$WORKSPACE" in
    new|n)
      xdotool set_num_desktops "$((n+1))" 2>/dev/null || true
      n="$(xdotool get_num_desktops 2>/dev/null || echo "$n")"
      printf '%s\n' "$(( n>0 ? n-1 : 0 ))" ;;
    *[!0-9]*|"")
      echo ">> WARN: bad --workspace '$WORKSPACE' (want a number or 'new'); skipping" >&2
      return 1 ;;
    *)
      if (( WORKSPACE >= n )); then
        xdotool set_num_desktops "$((WORKSPACE+1))" 2>/dev/null || true
        n="$(xdotool get_num_desktops 2>/dev/null || echo "$n")"
        if (( WORKSPACE >= n )); then
          echo ">> WARN: workspace $WORKSPACE out of range (have $n); clamping to $((n-1))" >&2
          printf '%s\n' "$(( n-1 ))"; return 0
        fi
      fi
      printf '%s\n' "$WORKSPACE" ;;
  esac
}

park_workspace(){
  [[ -n "$WORKSPACE" ]] || return 0
  xdotool get_num_desktops >/dev/null 2>&1 || { echo ">> WARN: WM exposes no EWMH workspaces; --workspace ignored" >&2; return 0; }
  local target; target="$(resolve_workspace_target)" || return 0
  xdotool set_desktop_for_window "$WID" "$target" && echo ">> parked on workspace $target"
}
