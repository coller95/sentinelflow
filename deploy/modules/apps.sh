#!/usr/bin/env bash
# apps.sh — build the run env + launch app instances. Source me.

build_run_env(){
  RUN_ENV=( "WINEPREFIX=$PREFIX" )
  # --net runs wine via 'runuser', which scrubs the environment — carry the X11
  # bits and HOME across explicitly so wine can reach the display.
  if (( NET )); then
    RUN_ENV+=( "DISPLAY=${DISPLAY:-:0}" "XAUTHORITY=${XAUTHORITY:-$HOME/.Xauthority}" "HOME=$HOME" )
  fi
  (( ${#ENV_KV[@]} )) && RUN_ENV+=( "${ENV_KV[@]}" ) || true
}

# run_app $n — launch one app. NS_RUN is empty in normal mode; in --net mode it
# is the 'sudo ip netns exec ... runuser ...' prefix that drops the app into the
# instance's network namespace as your user.
run_app(){
  local n="$1" log="${TMPDIR:-/tmp}/wine-${NAME}-${1}.log"
  # append: a relaunch must not wipe the previous run's crash output
  echo "── run $(date '+%F %T') ──" >>"$log"
  "${NS_RUN[@]}" env "${RUN_ENV[@]}" wine explorer "/desktop=$NAME,$RES" "$APP" >>"$log" 2>&1 &
  ALL_PIDS+=("$!")
  echo ">> [$n] $APP (pid=$! log=$log)"
}
