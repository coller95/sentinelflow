#!/usr/bin/env bash
# apps.sh — build run env + launch app instances. Source me.

build_run_env(){
  RUN_ENV=( "WINEPREFIX=$PREFIX" )
  ((${#ENV_KV[@]})) && RUN_ENV+=( "${ENV_KV[@]}" ) || true
}

run_app(){
  local n="$1" log="${TMPDIR:-/tmp}/wine-${NAME}-${1}.log"
  env "${RUN_ENV[@]}" wine explorer "/desktop=$NAME,$RES" "$APP" >"$log" 2>&1 &
  ALL_PIDS+=("$!")
  echo ">> [$n] $APP (pid=$! log=$log)"
}
