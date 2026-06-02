#!/usr/bin/env bash
# wc3.sh — launch ONE Warcraft III + Garena Universal MH instance, closed-loop.
# Flow (event-based, vision-confirmed):
#   1. start MH in its own wine desktop/prefix
#   2. wait for MH window, vision-click "Start Garena Universal MapHack"
#   3. wait until vision sees "MH Enabled - start W3 now"
#   4. start war3 in the SAME prefix (MH injects into it)
# Blocks until Ctrl+C, then kills the instance.
#
# Usage:  ./wc3.sh [--fullscreen] [--workspace N] [PREFIX]
#   PREFIX        = wine prefix path (default: $HOME/.wine)
#   --workspace N = park this instance's window on GNOME/EWMH workspace N
#                   (0-indexed). Capture/input are workspace-independent, so
#                   you can watch one workspace while the fleet runs on others.
#   multiple instances = separate terminals, different prefixes + workspaces:
#     ./wc3.sh -w 0 ~/.wineGame1 ; ./wc3.sh -w 1 ~/.wineGame2 ; ./wc3.sh -w 2 ~/.wineGame3
set -u

# optional leading flags: --fullscreen/-f, --workspace/-w N
while :; do case "${1:-}" in
  --fullscreen|-f) FULLSCREEN=1; shift ;;
  --workspace|-w)  WORKSPACE="${2:-}"; shift 2 ;;
  *) break ;;
esac; done

PREFIX="${1:-$HOME/.wine}"
HERE="$(cd "$(dirname "$0")" && pwd)"
VISION="$HERE/vision.py"
OK_TPL="$HERE/tpl/ok.png"
BTN_TPL="$HERE/tpl/btn.png"
EN_TPL="$HERE/tpl/enabled.png"

WC3='C:\Program Files (x86)\Warcraft III'
RES='1024x768'
# RENDERER selects war3's graphics + present path. This matters for capture:
#   dxvk   (default) -> war3 D3D8 routed through DXVK d8vk on Mesa lavapipe
#                       (software Vulkan). Mesa's X11 software WSI copies each
#                       frame into the X *window pixmap*, so get_image/scrot read
#                       real pixels. Run setup-prefix.sh once per prefix first.
#   opengl (fallback)-> war3 -opengl forced down the llvmpipe drisw XPutImage path.
# Direct GPU rendering (DRI3) presents out-of-band and reads back BLACK — never use
# it for a capturable instance.
RENDERER="${RENDERER:-dxvk}"
LVP_ICD="${LVP_ICD:-/usr/share/vulkan/icd.d/lvp_icd.json}"
if [[ "$RENDERER" == "dxvk" ]]; then
  WAR3_ARGS=()                                  # default D3D8 -> DXVK loads d3d8.dll
  WAR3_ENV=(VK_ICD_FILENAMES="$LVP_ICD" WINEDLLOVERRIDES='d3d8,d3d9,dxgi=n')
else
  WAR3_ARGS=(-opengl)
  WAR3_ENV=(LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe LIBGL_DRI3_DISABLE=1 MESA_LOADER_DRIVER_OVERRIDE=llvmpipe)
fi
# FULLSCREEN=1 -> war3 runs native on main screen (no wine desktop wrapper).
# default 0    -> war3 runs inside the wine desktop window.
# MH always stays in the wine desktop (vision needs it). Set via env or --fullscreen flag.
FULLSCREEN="${FULLSCREEN:-0}"
# WORKSPACE="" -> stay on the current workspace; set a 0-indexed number (env or
# --workspace N) to park this instance on its own GNOME/EWMH workspace.
WORKSPACE="${WORKSPACE:-}"
# Input/automation is driven by SentinelFlow (attach to the wine desktop window
# and inject via xdotool --window); no in-prefix AutoClicker needed.
WIN_TIMEOUT=20          # secs to wait for MH window to appear
CLICK_TIMEOUT=20        # secs to find+click Start button
ENABLE_TIMEOUT=20       # secs to confirm "MH Enabled"

NAME=$(basename "$PREFIX")
DESK="$NAME - Wine Desktop"
[[ -e "$PREFIX/drive_c/Program Files (x86)/Warcraft III/Garena Universal MH.exe" ]] \
  || { echo "ERR: MH missing in $PREFIX" >&2; exit 1; }

find_win(){ xdotool search --name "$DESK" 2>/dev/null | head -1; }

# Park a window on workspace $WORKSPACE (no-op if WORKSPACE unset). Needs an
# EWMH-aware WM (GNOME/mutter); harmless warning otherwise.
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

cleanup(){
  echo; echo ">> Ctrl+C — killing $NAME"
  WINEPREFIX="$PREFIX" wineserver -k 2>/dev/null
  exit 0
}
trap cleanup INT TERM
fail(){ echo "ERR: $*" >&2; cleanup; }

echo ">> [$NAME] launch MH"
WINEPREFIX="$PREFIX" wine explorer "/desktop=$NAME,$RES" \
  "$WC3\\Garena Universal MH.exe" >"$PREFIX/mh.log" 2>&1 &

echo ">> [$NAME] wait for MH window"
end=$((SECONDS + WIN_TIMEOUT)); wid=""
while [[ $SECONDS -lt $end ]]; do wid=$(find_win); [[ -n $wid ]] && break; sleep 0.5; done
[[ -n $wid ]] || fail "MH window not found in ${WIN_TIMEOUT}s"
echo ">> [$NAME] MH window = $wid"

# Non-fullscreen: war3 joins this same wine desktop window, so parking it now
# moves the whole instance. (Fullscreen war3 is parked separately below.)
[[ "$FULLSCREEN" == 1 ]] || move_to_workspace "$wid"

echo ">> [$NAME] dismiss info popup (OK)"
python3 "$VISION" click "$wid" "$OK_TPL" --timeout "$CLICK_TIMEOUT" \
  || fail "info popup OK not found/clicked"

echo ">> [$NAME] vision-click Start MapHack"
python3 "$VISION" click "$wid" "$BTN_TPL" --timeout "$CLICK_TIMEOUT" \
  || fail "Start button not found/clicked"

echo ">> [$NAME] confirm MH Enabled"
python3 "$VISION" wait "$wid" "$EN_TPL" --timeout "$ENABLE_TIMEOUT" \
  || fail "MH did not report Enabled"

if [[ "$FULLSCREEN" == 1 ]]; then
  echo ">> [$NAME] launch war3 FULLSCREEN on main screen ($RENDERER)"
  # no /desktop wrapper -> war3 renders natively; its own video pref (fullscreen) applies
  env WINEPREFIX="$PREFIX" "${WAR3_ENV[@]}" \
    wine "$WC3\\war3.exe" "${WAR3_ARGS[@]}" \
    >"$PREFIX/war3.log" 2>&1 &
  # park the native war3 window once it appears
  if [[ -n "$WORKSPACE" ]]; then
    for _ in $(seq 1 20); do
      w3=$(xdotool search --name "Warcraft III" 2>/dev/null | head -1)
      [[ -n "$w3" ]] && { move_to_workspace "$w3"; break; }
      sleep 0.5
    done
  fi
else
  echo ">> [$NAME] launch war3 in wine desktop ($RENDERER)"
  env WINEPREFIX="$PREFIX" "${WAR3_ENV[@]}" \
    wine explorer "/desktop=$NAME,$RES" \
    "$WC3\\war3.exe" "${WAR3_ARGS[@]}" >"$PREFIX/war3.log" 2>&1 &
fi

echo ">> [$NAME] running. Ctrl+C to kill."
wait
