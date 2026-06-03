# shellcheck shell=bash
# window.sh — X11 window placement helpers for launch.sh. Find/wait the wine
# desktop window, park windows on a GNOME/EWMH workspace. Needs xdotool; reads
# NAME/DESK/RES/WORKSPACE/WIN_TIMEOUT from launch.sh's env. No app specifics.

find_win(){ xdotool search --name "$DESK" 2>/dev/null | head -1; }

# Poll find_win up to WIN_TIMEOUT seconds; echo the wid and return 0 on
# success, return 1 on timeout.
wait_win(){
  local end=$((SECONDS + WIN_TIMEOUT)) wid=""
  while [[ $SECONDS -lt $end ]]; do
    wid=$(find_win); [[ -n $wid ]] && { echo "$wid"; return 0; }
    sleep 0.5
  done
  return 1
}

# Fullscreen APP_MAIN renders native (no wine desktop), so it has its own X
# window distinct from $DESK. Wait for the first new wine window and park it.
# No-op if WORKSPACE unset.
park_native_app(){
  [[ -n "$WORKSPACE" ]] || return 0
  local w end=$((SECONDS + WIN_TIMEOUT))
  while [[ $SECONDS -lt $end ]]; do
    w=$(xdotool search --class wine 2>/dev/null | tail -1)
    [[ -n "$w" ]] && { move_to_workspace "$w"; return 0; }
    sleep 0.5
  done
  echo ">> [$NAME] WARN: native app window not found to park in ${WIN_TIMEOUT}s"
}

# Park a window on workspace $WORKSPACE. No-op if WORKSPACE unset; numeric guard.
# Needs an EWMH-aware WM (GNOME/mutter); harmless warning otherwise.
move_to_workspace(){
  local win="$1"
  [[ -n "$WORKSPACE" ]] || return 0
  [[ "$WORKSPACE" =~ ^[0-9]+$ ]] \
    || { echo ">> [$NAME] WARN: WORKSPACE='$WORKSPACE' not a number, skipping"; return 0; }
  if xdotool set_desktop_for_window "$win" "$WORKSPACE" 2>/dev/null; then
    echo ">> [$NAME] parked window $win on workspace $WORKSPACE"
  else
    echo ">> [$NAME] WARN: could not move window $win to workspace $WORKSPACE (no EWMH WM?)"
  fi
}
