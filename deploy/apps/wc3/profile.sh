# shellcheck shell=bash
# -----------------------------------------------------------------------------
# deploy/apps/wc3/profile.sh - Warcraft III app PLUG, sourced by deploy/fleet.sh
#
# Sourced (not executed): no shebang. $0 is fleet.sh, so paths to this file's
# own siblings are computed from ${BASH_SOURCE[0]}.
#
# Sets the PROFILE CONTRACT vars (APP_MAIN, APP_RES, APP_ENV, APP_ARGS) and the
# optional hooks app_check_prefix / app_launch_helper / app_pre_main. RENDERER
# (dxvk default | opengl) is a WC3 concern handled here, not in fleet.sh.
# -----------------------------------------------------------------------------

# --- Paths -------------------------------------------------------------------
WC3='C:\\Program Files (x86)\\Warcraft III'
APP_RES=1024x768
APP_MAIN="$WC3\\war3.exe"

# --- Renderer -> APP_ENV / APP_ARGS -----------------------------------------
# dxvk:   DXVK d3d8/d3d9/dxgi on a Vulkan ICD (lavapipe by default).
# opengl: native -opengl path forced onto llvmpipe software GL.
: "${RENDERER:=dxvk}"
: "${LVP_ICD:=/usr/share/vulkan/icd.d/lvp_icd.json}"

case "$RENDERER" in
  opengl)
    APP_ARGS=(-opengl)
    APP_ENV=(
      LIBGL_ALWAYS_SOFTWARE=1
      GALLIUM_DRIVER=llvmpipe
      LIBGL_DRI3_DISABLE=1
      MESA_LOADER_DRIVER_OVERRIDE=llvmpipe
    )
    ;;
  dxvk|*)
    APP_ARGS=()
    APP_ENV=(
      VK_ICD_FILENAMES="$LVP_ICD"
      WINEDLLOVERRIDES='d3d8,d3d9,dxgi=n'
    )
    ;;
esac

# --- Timeouts ----------------------------------------------------------------
CLICK_TIMEOUT=20
ENABLE_TIMEOUT=20

# --- Hooks -------------------------------------------------------------------

# Preflight: the Garena MapHack helper AND war3.exe must exist in the prefix.
app_check_prefix() {
  local base="$PREFIX/drive_c/Program Files (x86)/Warcraft III"
  local mh="$base/Garena Universal MH.exe"
  local war3="$base/war3.exe"
  if [[ ! -f "$mh" ]]; then
    echo "ERR: missing Garena Universal MH.exe in prefix: $mh" >&2
    return 1
  fi
  if [[ ! -f "$war3" ]]; then
    echo "ERR: missing war3.exe in prefix: $war3" >&2
    return 1
  fi
  return 0
}

# Helper that OWNS the wine desktop: launch Garena MapHack into the desktop so
# war3.exe (launched later by fleet into the SAME desktop) gets injected.
app_launch_helper() {
  WINEPREFIX="$PREFIX" wine explorer "/desktop=$NAME,$RES" \
    "$WC3\\Garena Universal MH.exe" >"$PREFIX/mh.log" 2>&1 &
}

# Vision sequence run against the helper's window before launching war3.
#   $1 = window id (wid)
# Dismiss info popup (ok), press Start MapHack (btn), confirm MH Enabled.
app_pre_main() {
  local wid="$1"
  local here vision tpl
  here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  vision="$here/../../vision.py"
  tpl="$here/tpl"

  python3 "$vision" click "$wid" "$tpl/ok.png"      --timeout "$CLICK_TIMEOUT"  || return 1
  python3 "$vision" click "$wid" "$tpl/btn.png"     --timeout "$CLICK_TIMEOUT"  || return 1
  python3 "$vision" wait  "$wid" "$tpl/enabled.png" --timeout "$ENABLE_TIMEOUT" || return 1
  return 0
}
