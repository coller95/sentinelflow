#!/usr/bin/env bash
# bootstrap.sh — create a fresh 64-bit (wow64) wine prefix with DXVK.
# App-agnostic. The only setup step that exists today.
#
# Needs wine >=9.0 (wow64 single-arch prefix, no 32-bit multilib) + winetricks.
# Missing ones are apt-installed; re-runs skip apt when both are present.
#
# Usage:  ./bootstrap.sh <PREFIX>
#   PREFIX = wine prefix path to create (e.g. ~/.wineGame1)
set -euo pipefail

PREFIX="${1:?need PREFIX (e.g. ~/.wineGame1)}"

# ── ensure wine + winetricks ──
NEED=()
command -v wine       >/dev/null || NEED+=(wine)
command -v winetricks >/dev/null || NEED+=(winetricks)
if ((${#NEED[@]})); then
  echo ">> missing: ${NEED[*]}"
  command -v apt-get >/dev/null || { echo "ERR: apt-get not found. Install: ${NEED[*]}" >&2; exit 1; }
  SUDO=""; [[ $EUID -ne 0 ]] && SUDO="sudo"
  $SUDO apt-get update
  $SUDO apt-get install -y "${NEED[@]}"
else
  echo ">> wine + winetricks OK"
fi

# ── fresh wow64 prefix ──
echo ">> wineboot: init wow64 prefix at $PREFIX"
WINEARCH=win64 WINEPREFIX="$PREFIX" wineboot -i

# ── DXVK (winetricks): d3d9/d3d10/d3d11/dxgi ──
echo ">> winetricks: install dxvk into $PREFIX"
WINEPREFIX="$PREFIX" winetricks -q dxvk

echo ">> bootstrapped $PREFIX"
