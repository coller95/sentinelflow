#!/usr/bin/env bash
# bootstrap.sh — create a fresh, capturable wine env in a NEW prefix.
# App-agnostic: just a clean 64-bit (wow64) prefix + DXVK via winetricks.
# Game files and per-app provisioning (apps/<name>/setup.sh) come LATER.
#
# Needs `wine` + `winetricks` on PATH (system packages):
#   sudo apt install wine winetricks      # or your distro's equivalent
#
# Usage:  ./bootstrap.sh <PREFIX>
#   PREFIX = wine prefix path to create (e.g. ~/.wineGame1)
set -euo pipefail

PREFIX="${1:?need PREFIX (e.g. ~/.wineGame1)}"

# ── require the tools (don't auto-apt; just tell the user) ──
for t in wine winetricks; do
  command -v "$t" >/dev/null || { echo "ERR: '$t' not on PATH. Install: sudo apt install wine winetricks" >&2; exit 1; }
done

# ── 1. fresh 64-bit (wow64) prefix ──
echo ">> wineboot: init wow64 prefix at $PREFIX"
WINEARCH=win64 WINEPREFIX="$PREFIX" wineboot -i

# ── 2. DXVK (winetricks). DXVK 2.4+ ships d3d8/d3d9/dxgi for the capture path. ──
echo ">> winetricks: install dxvk into $PREFIX"
WINEPREFIX="$PREFIX" winetricks -q dxvk

echo ">> bootstrapped $PREFIX. Next: drop in game files, then run apps/<name>/setup.sh $PREFIX"
