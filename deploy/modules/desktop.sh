#!/usr/bin/env bash
# desktop.sh — desktop naming + window lifecycle. Source me.

derive_name(){
  NAME="${NAME:-$(basename "$PREFIX")}"
  NAME="${NAME#"${NAME%%[!.]*}"}"  # strip leading dots (~/.wineTest -> wineTest)
  WIN_NAME="$NAME - Wine Desktop"
}

wait_for_window(){
  echo ">> waiting for window: '$WIN_NAME' (<=${TIMEOUT}s)"
  WID=""
  for ((i=0; i<TIMEOUT*2; i++)); do
    WID="$(xdotool search --name "^${WIN_NAME}$" 2>/dev/null | head -1 || true)"
    [[ -n "$WID" ]] && break
    sleep 0.5
  done
  [[ -n "$WID" ]] || die "desktop window '$WIN_NAME' did not appear in ${TIMEOUT}s"
  echo ">> desktop window id: $WID"
}

park_workspace(){
  if [[ -n "$WORKSPACE" ]] && xdotool get_num_desktops >/dev/null 2>&1; then
    xdotool set_desktop_for_window "$WID" "$WORKSPACE" && echo ">> parked on workspace $WORKSPACE"
  fi
}
