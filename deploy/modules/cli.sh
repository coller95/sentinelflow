#!/usr/bin/env bash
# cli.sh — usage text + argument parsing. Source me.

# The usage() function reads the entry script's header for help text.
# This function signature is FIXED and reads from $0 (the entry point).
usage(){ sed -n '2,/^set -euo/p' "$0" | sed 's/^# \{0,1\}//;$d'; exit "${1:-0}"; }

# parse_cli() — parses command-line arguments and fills shared globals.
# Takes "$@" as input; sets plain (non-local) globals visible to caller.
parse_cli(){
  # Set defaults
  APP="notepad"
  COUNT=3
  PREFIX=""
  NAME=""
  RES="1024x768"
  WORKSPACE=""
  TIMEOUT=30
  ENV_KV=()

  # Parse arguments with the original while/case loop
  while (($#)); do
    case "$1" in
      -p|--prefix)    PREFIX="${2:?}"; shift 2 ;;
      -n|--name)      NAME="${2:?}"; shift 2 ;;
      -r|--res)       RES="${2:?}"; shift 2 ;;
      -w|--workspace) WORKSPACE="${2:?}"; shift 2 ;;
      -e|--env)       ENV_KV+=("${2:?}"); shift 2 ;;
      -t|--timeout)   TIMEOUT="${2:?}"; shift 2 ;;
      -h|--help)      usage 0 ;;
      -*)             die "unknown flag '$1' (see --help)" ;;
      *)              die "unexpected arg '$1' (apps are fixed; see --help)" ;;
    esac
  done
}
