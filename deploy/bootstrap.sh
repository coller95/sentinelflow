#!/usr/bin/env bash
# bootstrap.sh — wine prefix lifecycle + per-app install. App-agnostic core.
#
# Modes:
#   bootstrap.sh <PREFIX>                 create a fresh wow64 prefix + DXVK
#   bootstrap.sh --app NAME <PREFIX>      ensure PREFIX exists, then run the
#                                         deploy/apps/NAME.app profile's
#                                         app_install() into it (if defined)
#   bootstrap.sh --save <PREFIX> <OUT>    snapshot a ready prefix -> OUT (.tar.zst)
#   bootstrap.sh --restore <IN> <PREFIX>  restore a snapshot -> empty PREFIX
#   bootstrap.sh --help
#
# Needs wine >=9.0 (wow64, no 32-bit multilib) + winetricks to create; tar+zstd
# to save/restore. Missing wine/winetricks are apt-installed (Debian); on other
# distros install them first.
#
# Snapshot caveat: a wine prefix bakes the username/home into user.reg and
# dosdevices — restore to the SAME username. Stop launch.sh instances before
# --save so the files are quiescent.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# usage() prints this script's header (above 'set -euo'); keep the block intact.
usage(){ sed -n '2,/^set -euo/p' "$0" | sed 's/^# \{0,1\}//;$d'; exit "${1:-0}"; }

create_prefix(){
  local prefix="$1" NEED=()
  command -v wine       >/dev/null || NEED+=(wine)
  command -v winetricks >/dev/null || NEED+=(winetricks)
  if ((${#NEED[@]})); then
    echo ">> missing: ${NEED[*]}"
    command -v apt-get >/dev/null || { echo "ERR: apt-get not found. Install: ${NEED[*]}" >&2; exit 1; }
    local SUDO=""; [[ $EUID -ne 0 ]] && SUDO="sudo"
    $SUDO apt-get update
    $SUDO apt-get install -y "${NEED[@]}"
  else
    echo ">> wine + winetricks OK"
  fi
  echo ">> wineboot: init wow64 prefix at $prefix"
  WINEARCH=win64 WINEPREFIX="$prefix" wineboot -i
  echo ">> winetricks: install dxvk into $prefix"
  WINEPREFIX="$prefix" winetricks -q dxvk
  echo ">> bootstrapped $prefix"
}

need_tar_zstd(){
  command -v tar >/dev/null && command -v zstd >/dev/null \
    || { echo "ERR: need tar + zstd for save/restore" >&2; exit 1; }
}

save_prefix(){
  local prefix="$1" out="$2"
  [[ -d "$prefix" ]] || { echo "ERR: prefix not found: $prefix" >&2; exit 1; }
  need_tar_zstd
  echo ">> saving $prefix -> $out (can be large; stop instances first)"
  tar -C "$prefix" -cpf - . | zstd -T0 -q -f -o "$out"
  echo ">> saved $(du -h "$out" | cut -f1) -> $out"
}

restore_prefix(){
  local in="$1" prefix="$2"
  [[ -f "$in" ]] || { echo "ERR: snapshot not found: $in" >&2; exit 1; }
  need_tar_zstd
  if [[ -e "$prefix" && -n "$(ls -A "$prefix" 2>/dev/null)" ]]; then
    echo "ERR: $prefix exists and is not empty — refusing to overwrite" >&2; exit 1
  fi
  mkdir -p "$prefix"
  echo ">> restoring $in -> $prefix"
  zstd -dc "$in" | tar -C "$prefix" -xpf -
  echo ">> restored $prefix (must match the source username/home)"
}

app_bootstrap(){
  local name="$1" prefix="$2" pf="$HERE/apps/$1.app"
  [[ "$name" =~ ^[A-Za-z0-9._-]+$ && -f "$pf" ]] \
    || { echo "ERR: no profile deploy/apps/$name.app" >&2; exit 1; }
  [[ -d "$prefix" ]] || create_prefix "$prefix"
  # shellcheck disable=SC1090
  source "$pf"
  if declare -F app_install >/dev/null; then
    echo ">> running '$name' app_install into $prefix"
    WINEPREFIX="$prefix" app_install
  else
    echo ">> profile '$name' defines no app_install — launch-only, nothing to install"
  fi
}

case "${1:-}" in
  -h|--help) usage 0 ;;
  --app)     [[ $# -eq 3 ]] || usage 1; app_bootstrap "$2" "$3" ;;
  --save)    [[ $# -eq 3 ]] || usage 1; save_prefix "$2" "$3" ;;
  --restore) [[ $# -eq 3 ]] || usage 1; restore_prefix "$2" "$3" ;;
  -*)        echo "ERR: unknown flag '$1' (see --help)" >&2; usage 1 ;;
  "")        usage 1 ;;
  *)         [[ $# -eq 1 ]] || usage 1; create_prefix "$1" ;;
esac
