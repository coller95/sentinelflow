#!/usr/bin/env bash
# bootstrap.sh — make a NEW machine + a NEW prefix ready to run the wine-fleet.
# App-agnostic. Two stages:
#   1. ensure system packages (apt) the generic harness needs — idempotent,
#      only calls `sudo apt` when something is actually missing.
#   2. create a clean 64-bit (wow64) wine prefix + DXVK via winetricks.
# Game files and per-app provisioning (apps/<name>/setup.sh) come LATER.
#
# Usage:  ./bootstrap.sh <PREFIX>
#   PREFIX = wine prefix path to create (e.g. ~/.wineGame1)
set -euo pipefail

PREFIX="${1:?need PREFIX (e.g. ~/.wineGame1)}"

# ── system packages the generic harness uses ──
#   wine/winetricks        wine + DXVK install
#   xdotool/scrot          window-targeted input + capture
#   mesa-vulkan-drivers    lavapipe software Vulkan ICD (the capturable present path)
#   libvulkan1/vulkan-tools Vulkan loader (+ vulkaninfo for debugging)
#   python3 + numpy/opencv/xlib   vision.py template-match clicking
#   iproute2               `ip` for launch-netns.sh
#   xvfb                   headless X display for fleet nodes
APT_PKGS=(
  wine winetricks xdotool scrot
  mesa-vulkan-drivers libvulkan1 vulkan-tools
  python3 python3-numpy python3-opencv python3-xlib
  iproute2 xvfb
)

# Probe what's already usable; only escalate to apt if something is missing.
missing_pkgs() {
  local need=()
  command -v wine        >/dev/null || need+=(wine)
  command -v winetricks  >/dev/null || need+=(winetricks)
  command -v xdotool     >/dev/null || need+=(xdotool)
  command -v scrot       >/dev/null || need+=(scrot)
  command -v ip          >/dev/null || need+=(iproute2)
  command -v Xvfb        >/dev/null || need+=(xvfb)
  command -v vulkaninfo  >/dev/null || need+=(vulkan-tools)
  [[ -e /usr/share/vulkan/icd.d/lvp_icd.json ]] || need+=(mesa-vulkan-drivers libvulkan1)
  python3 -c 'import numpy' 2>/dev/null || need+=(python3-numpy)
  python3 -c 'import cv2'   2>/dev/null || need+=(python3-opencv)
  python3 -c 'import Xlib'  2>/dev/null || need+=(python3-xlib)
  ((${#need[@]})) && printf '%s\n' "${need[@]}"
}

mapfile -t NEED < <(missing_pkgs)
if ((${#NEED[@]})); then
  echo ">> missing packages: ${NEED[*]}"
  command -v apt-get >/dev/null || {
    echo "ERR: apt-get not found. Install manually: ${APT_PKGS[*]}" >&2; exit 1; }
  SUDO=""; [[ $EUID -ne 0 ]] && SUDO="sudo"
  $SUDO apt-get update
  $SUDO apt-get install -y "${NEED[@]}"
else
  echo ">> system packages OK"
fi

# ── 1. fresh 64-bit (wow64) prefix ──
echo ">> wineboot: init wow64 prefix at $PREFIX"
WINEARCH=win64 WINEPREFIX="$PREFIX" wineboot -i

# ── 2. DXVK (winetricks). Installs d3d9/d3d10/d3d11/dxgi for the capture path. ──
#    NOTE: winetricks does NOT deploy d3d8 — Direct3D8 apps (war3) get d8vk d3d8
#    later via apps/<name>/setup.sh -> lib/capture.sh.
echo ">> winetricks: install dxvk into $PREFIX"
WINEPREFIX="$PREFIX" winetricks -q dxvk

echo ">> bootstrapped $PREFIX. Next: drop in game files, then run apps/<name>/setup.sh $PREFIX"
