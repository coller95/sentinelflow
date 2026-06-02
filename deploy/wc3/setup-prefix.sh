#!/usr/bin/env bash
# setup-prefix.sh — one-time provisioning of a wine prefix so war3 renders a
# CAPTURABLE frame and reaches its menu (no 640x480 black stall).
#
# What it does:
#   1. Installs DXVK d8vk x32 DLLs (d3d8/d3d9/dxgi) into the prefix syswow64 so
#      war3's Direct3D8 is routed through DXVK on Mesa lavapipe. DXVK's X11
#      software WSI copies each frame into the X window pixmap, which is what
#      makes get_image/scrot read real pixels instead of black. (Direct GPU/DRI3
#      rendering presents out-of-band and reads back black.)
#   2. Seeds War3Preferences.txt + the Warcraft III\Video registry for windowed
#      1024x768 low-detail startup, so war3 advances past the 640x480 first-run
#      splash to the menu.
#   3. Moves the intro Movies aside (a blocked/looping movie stalls device init
#      at a black splash).
#
# Usage:  ./setup-prefix.sh <PREFIX>
#   PREFIX = wine prefix path (e.g. ~/.wineGame1)
# Override DXVK source dir with DXVK_X32_DIR=/path/to/dxvk/x32
set -euo pipefail

PREFIX="${1:?need PREFIX (e.g. ~/.wineGame1)}"
WINUSER="${WINUSER:-$USER}"
WC3DIR="$PREFIX/drive_c/Program Files (x86)/Warcraft III"
SYSWOW="$PREFIX/drive_c/windows/syswow64"

[[ -e "$WC3DIR/war3.exe" ]] || { echo "ERR: war3.exe not found in $WC3DIR" >&2; exit 1; }
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
  echo "ERR: DXVK x32 d8vk DLLs not found. Install a DXVK with d8vk (d3d8.dll) and"
  echo "     set DXVK_X32_DIR=/path/to/dxvk/x32 (must contain d3d8/d3d9/dxgi.dll)." >&2
  exit 1
}
echo ">> DXVK x32 source: $DXVK_DIR"

# ── 1. install DXVK DLLs (back up wine builtins once) ──
for d in d3d8 d3d9 dxgi; do
  tgt="$SYSWOW/$d.dll"
  [[ -f "$tgt" && ! -f "$tgt.wineorig" ]] && cp -n "$tgt" "$tgt.wineorig" || true
  cp -f "$DXVK_DIR/$d.dll" "$tgt"
  echo ">> installed $d.dll"
done

# ── 2. seed War3Preferences.txt (Documents + install dir; path is locale-ish) ──
DOCS="$PREFIX/drive_c/users/$WINUSER/Documents"
[[ -d "$DOCS" ]] || DOCS="$PREFIX/drive_c/users/$WINUSER/My Documents"
mkdir -p "$DOCS/Warcraft III"
PREF=$'windowed=1\nreslowdetail=1\nreswidth=1024\nresheight=768\ngxapi=0\n'
printf '%s' "$PREF" > "$DOCS/Warcraft III/War3Preferences.txt"
printf '%s' "$PREF" > "$WC3DIR/War3Preferences.txt"
echo ">> seeded War3Preferences.txt"

# ── 2b. Video registry (windowed 1024x768; Gfx OpenGL=0 for the DXVK D3D8 path) ──
REG="$(mktemp --suffix=.reg)"
cat > "$REG" <<'EOF'
Windows Registry Editor Version 5.00

[HKEY_CURRENT_USER\Software\Blizzard Entertainment\Warcraft III\Video]
"reswidth"=dword:00000400
"resheight"=dword:00000300
"Gfx OpenGL"=dword:00000000
EOF
WINEPREFIX="$PREFIX" wine regedit "$REG" 2>/dev/null && echo ">> applied Video registry"
rm -f "$REG"

# ── 3. disable intro movies (avoid black-splash stall) ──
if [[ -d "$WC3DIR/Movies" ]]; then
  mv "$WC3DIR/Movies" "$WC3DIR/Movies.off"
  echo ">> Movies -> Movies.off"
fi

echo ">> prefix $PREFIX provisioned. Launch with: ./wc3.sh $PREFIX"
