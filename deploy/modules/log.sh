#!/usr/bin/env bash
# log.sh — logging helpers. Source me.

log(){ echo ">> $*"; }
die(){ echo "ERR: $*" >&2; exit 1; }
