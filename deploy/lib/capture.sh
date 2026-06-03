#!/usr/bin/env bash
# capture.sh — make a D3D8/D3D9 wine game present into a CAPTURABLE frame.
#
# Generic helper: installs DXVK d8vk x32 DLLs (d3d8/d3d9/dxgi) into a prefix's
# syswow64 so the game's Direct3D8/9 is routed through DXVK on Mesa lavapipe.
# DXVK's X11 software WSI copies each rendered frame into the X window pixmap,
# which is what makes get_image/scrot/xdotool read real pixels instead of black.
# (Direct GPU/DRI3 presentation happens out-of-band and reads back black on a
# headless lavapipe setup.) Any 32-bit D3D8/9 wine game that needs a capturable
# present path can use this — there are NO game-specific bits here.
#
# Usage:  ./capture.sh <PREFIX>
#   PREFIX = wine prefix path (e.g. ~/.wineGame1), must be a 64-bit (wow64) prefix
# Override the DXVK x32 source dir with DXVK_X32_DIR=/path/to/dxvk/x32
#   (must contain d3d8.dll, i.e. a d8vk-enabled DXVK build).
set -euo pipefail

PREFIX="${1:?need PREFIX (e.g. ~/.wineGame1)}"
SYSWOW="$PREFIX/drive_c/windows/syswow64"

[[ -d "$SYSWOW" ]] || { echo "ERR: $SYSWOW missing (is this a 64-bit prefix?)" >&2; exit 1; }

# ── locate DXVK x32 d8vk DLLs ──
find_dxvk(){
  [[ -n "${DXVK_X32_DIR:-}" && -f "$DXVK_X32_DIR/d3d8.dll" ]] && { echo "$DXVK_X32_DIR"; return; }
  local c
  for c in \
    "$HOME"/.local/share/lutris/runtime/dxvk/*/x32 \
    /usr/share/dxvk/x32 \
    "$HOME"/.local/share/dxvk*/x32 ; do
    [[ -f "$c/d3d8.dll" ]] && { echo "$c"; return; }
  done
  return 1
}
DXVK_DIR="$(find_dxvk)" || {
  echo "ERR: DXVK x32 d8vk DLLs not found. Install a DXVK with d8vk (d3d8.dll) and" >&2
  echo "     set DXVK_X32_DIR=/path/to/dxvk/x32 (must contain d3d8/d3d9/dxgi.dll)." >&2
  exit 1
}
echo ">> DXVK x32 source: $DXVK_DIR"

# ── install DXVK DLLs (back up wine builtins once) ──
for d in d3d8 d3d9 dxgi; do
  tgt="$SYSWOW/$d.dll"
  [[ -f "$tgt" && ! -f "$tgt.wineorig" ]] && cp -n "$tgt" "$tgt.wineorig" || true
  cp -f "$DXVK_DIR/$d.dll" "$tgt"
  echo ">> installed $d.dll"
done

echo ">> wine-capture: DXVK d8vk present path installed into $SYSWOW"
