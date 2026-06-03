#!/usr/bin/env bash
# apps/wc3/setup.sh — one-time WC3-specific provisioning of a wine prefix so
# war3 reaches its menu in a CAPTURABLE windowed mode (no 640x480 black stall).
#
# This is the war3 plug of the prefix setup. The generic, capture-enabling DLL
# install (DXVK d8vk x32 d3d8/d3d9/dxgi into syswow64, so D3D8 routes through
# DXVK on lavapipe and presents a frame the X window can read back) lives in
# the reusable lib/capture.sh, which we call first. Everything below is
# war3-only: it seeds War3Preferences.txt + the Warcraft III\Video registry for
# windowed 1024x768 low-detail startup, and moves the intro Movies aside (a
# blocked/looping movie stalls device init at a black splash).
#
# Usage:  ./setup.sh <PREFIX>
#   PREFIX = wine prefix path (e.g. ~/.wineGame1)
# Override DXVK source dir (consumed by lib/capture.sh) with
#   DXVK_X32_DIR=/path/to/dxvk/x32
set -euo pipefail

PREFIX="${1:?need PREFIX (e.g. ~/.wineGame1)}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WINUSER="${WINUSER:-$USER}"
WC3DIR="$PREFIX/drive_c/Program Files (x86)/Warcraft III"

# ── require war3.exe before touching anything ──
[[ -e "$WC3DIR/war3.exe" ]] || { echo "ERR: war3.exe not found in $WC3DIR" >&2; exit 1; }

# ── 1. generic capture-enabling DLL install (DXVK d8vk x32) ──
"$HERE/../../lib/capture.sh" "$PREFIX"

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

echo ">> prefix $PREFIX provisioned. Launch with: ./launch.sh apps/wc3/config.sh $PREFIX"
