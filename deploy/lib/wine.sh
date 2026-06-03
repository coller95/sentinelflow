# shellcheck shell=bash
# wine.sh — spawn the profile's APP_MAIN under wine for launch.sh. Two shapes:
# native (true fullscreen, own X window) and into a wine virtual desktop
# (/desktop=NAME,RES). Reads PREFIX/NAME/RES/APP_MAIN/APP_ENV/APP_ARGS from
# fleet's env. No app specifics — renderer/env/args all come from the profile's
# arrays.

# Launch APP_MAIN natively (no wine desktop), backgrounded, logging to $PREFIX/app.log.
launch_native_main() {
  env WINEPREFIX="$PREFIX" "${APP_ENV[@]}" \
    wine "$APP_MAIN" "${APP_ARGS[@]}" >"$PREFIX/app.log" 2>&1 &
}

# Launch APP_MAIN into a wine virtual desktop (/desktop=NAME,RES), backgrounded,
# logging to $PREFIX/app.log.
launch_desktop_main() {
  env WINEPREFIX="$PREFIX" "${APP_ENV[@]}" \
    wine explorer "/desktop=$NAME,$RES" \
    "$APP_MAIN" "${APP_ARGS[@]}" >"$PREFIX/app.log" 2>&1 &
}
