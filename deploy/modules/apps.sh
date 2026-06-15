#!/usr/bin/env bash
# apps.sh — build the run env + launch app instances. Source me.

build_run_env(){
  RUN_ENV=( "WINEPREFIX=$PREFIX" )   # --own-prefix: launch.sh already repointed PREFIX
  # --net runs wine via 'runuser', which scrubs the environment — carry the X11
  # bits and HOME across explicitly so wine can reach the display. WINEPREFIX
  # rides in RUN_ENV above: 'env' applies it INSIDE the scrub, so it survives
  # the same way (this also covers the --own-prefix dir).
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
  if (( NO_DESKTOP )); then
    # No virtual desktop: run the app directly so it owns its own window ($WIN_TITLE).
    # A launcher-style game (war3.exe behind Frozen Throne.exe) detaches — the wine
    # front-end exits while the engine keeps running. Hold this member alive while
    # $HOLD_PROC lives so supervision tracks the GAME, not the front-end that quit.
    if [[ -n "$HOLD_PROC" ]]; then
      # set +e: the launcher front-end exits non-zero when it hands off to the
      # engine; under launch.sh's `set -e` that would abort this holder before it
      # starts babysitting. Disable errexit here — the while-loop alone bounds life.
      ( set +e
        "${NS_RUN[@]}" env "${RUN_ENV[@]}" wine "$APP" $APP_ARGS >>"$log" 2>&1
        for _ in $(seq 1 30); do pgrep -f "$HOLD_PROC" >/dev/null 2>&1 && break; sleep 1; done
        while pgrep -f "$HOLD_PROC" >/dev/null 2>&1; do sleep 2; done ) &
    else
      "${NS_RUN[@]}" env "${RUN_ENV[@]}" wine "$APP" $APP_ARGS >>"$log" 2>&1 &
    fi
  else
    "${NS_RUN[@]}" env "${RUN_ENV[@]}" wine explorer "/desktop=$NAME,$RES" "$APP" >>"$log" 2>&1 &
  fi
  ALL_PIDS+=("$!")
  echo ">> [$n] $APP (pid=$! log=$log)"
}
