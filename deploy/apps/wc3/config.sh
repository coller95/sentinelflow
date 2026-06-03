# shellcheck shell=bash
# -----------------------------------------------------------------------------
# apps/wc3/config.sh — Warcraft III plug, sourced by deploy/launch.sh.
#
# ONE job: tell fleet how to launch war3.exe (DXVK d3d8/d3d9/dxgi on lavapipe).
# Maphack is a SEPARATE concern — see apps/wc3/maphack.sh. Run that first if you
# want maphack injected into the same wine desktop, then launch via fleet.
#
# Sourced (not executed): no shebang. $0 is launch.sh.
# -----------------------------------------------------------------------------

WC3='C:\\Program Files (x86)\\Warcraft III'
APP_RES=1024x768
APP_MAIN="$WC3\\war3.exe"

# DXVK d3d8/d3d9/dxgi routed through a Vulkan ICD (lavapipe software by default).
: "${LVP_ICD:=/usr/share/vulkan/icd.d/lvp_icd.json}"
APP_ARGS=()
APP_ENV=(
  VK_ICD_FILENAMES="$LVP_ICD"
  WINEDLLOVERRIDES='d3d8,d3d9,dxgi=n'
)

# Preflight: war3.exe must exist in the prefix.
app_check_prefix() {
  local war3="$PREFIX/drive_c/Program Files (x86)/Warcraft III/war3.exe"
  [[ -f "$war3" ]] || { echo "ERR: missing war3.exe: $war3" >&2; return 1; }
}
