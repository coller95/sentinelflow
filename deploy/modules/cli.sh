#!/usr/bin/env bash
# cli.sh — usage text + argument parsing. Source me.

# usage() reads the entry script's header ($0) for help text. Keep verbatim.
usage(){ sed -n '2,/^set -euo/p' "$0" | sed 's/^# \{0,1\}//;$d'; exit "${1:-0}"; }

# parse_cli "$@" — fill shared globals (plain, not local).
parse_cli(){
  APP="notepad"; COUNT=3; COUNT_SET=0
  PREFIX=""; NAME=""; RES="1024x768"; WORKSPACE=""; TIMEOUT=30
  NET=0; PARENT=""; IP_REQ=""
  NODE=0; NODE_CMD=""
  OWN_PREFIX=0; OWN_PREFIX_DIR=""
  XVFB=0
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
      --node)         NODE=1; shift ;;
      --node-cmd)     NODE_CMD="${2:?}"; NODE=1; shift 2 ;;
      --no-node)      NODE=0; shift ;;
      --own-prefix)   OWN_PREFIX=1; shift ;;
      --wineprefix)   OWN_PREFIX_DIR="${2:?}"; OWN_PREFIX=1; shift 2 ;;
      --xvfb)         XVFB=1; shift ;;
      --net)          NET=1; shift ;;
      --parent)       PARENT="${2:?}"; shift 2 ;;
      --ip)           IP_REQ="${2:?}"; shift 2 ;;
      -h|--help)      usage 0 ;;
      -*)             die "unknown flag '$1' (see --help)" ;;
      *)              die "unexpected arg '$1' (see --help)" ;;
    esac
  done

  # --ip / --parent are netns-only knobs, so either one implies --net. Saves the
  # footgun of passing --ip alone and having it silently ignored.
  if [[ -n "$IP_REQ" || -n "$PARENT" ]]; then NET=1; fi

  # RES feeds wine /desktop=,WxH, the Xvfb screen and the node's seeded geometry
  [[ "$RES" =~ ^[0-9]+x[0-9]+$ ]] || die "bad --res '$RES' (want WxH, e.g. 1024x768)"
}
