#!/usr/bin/env bash
# cli.sh — usage text + argument parsing. Source me.

# usage() reads the entry script's header ($0) for help text. Keep verbatim.
usage(){ sed -n '2,/^set -euo/p' "$0" | sed 's/^# \{0,1\}//;$d'; exit "${1:-0}"; }

# parse_cli "$@" — fill shared globals (plain, not local).
parse_cli(){
  APP="notepad"; COUNT=3; COUNT_SET=0
  PREFIX=""; NAME=""; RES="1024x768"; WORKSPACE=""; TIMEOUT=30
  NET=0; PARENT=""; IP_REQ=""
  ENV_KV=()

  while (( $# )); do
    case "$1" in
      -p|--prefix)    PREFIX="${2:?}"; shift 2 ;;
      -n|--name)      NAME="${2:?}"; shift 2 ;;
      -r|--res)       RES="${2:?}"; shift 2 ;;
      -w|--workspace) WORKSPACE="${2:?}"; shift 2 ;;
      -e|--env)       ENV_KV+=("${2:?}"); shift 2 ;;
      -t|--timeout)   TIMEOUT="${2:?}"; shift 2 ;;
      -a|--app)       APP="${2:?}"; shift 2 ;;
      -c|--count)     COUNT="${2:?}"; COUNT_SET=1; shift 2 ;;
      --net)          NET=1; shift ;;
      --parent)       PARENT="${2:?}"; shift 2 ;;
      --ip)           IP_REQ="${2:?}"; shift 2 ;;
      -h|--help)      usage 0 ;;
      -*)             die "unknown flag '$1' (see --help)" ;;
      *)              die "unexpected arg '$1' (see --help)" ;;
    esac
  done
}
