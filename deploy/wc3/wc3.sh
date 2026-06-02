#!/usr/bin/env bash
# wc3.sh — launch ONE Warcraft III + Garena Universal MH instance, closed-loop.
# Flow (event-based, vision-confirmed):
#   1. start MH in its own wine desktop/prefix
#   2. wait for MH window, vision-click "Start Garena Universal MapHack"
#   3. wait until vision sees "MH Enabled - start W3 now"
#   4. start war3 in the SAME prefix (MH injects into it)
# Blocks until Ctrl+C, then kills the instance.
#
# Usage:  ./wc3.sh [PREFIX]
#   PREFIX = wine prefix path (default: $HOME/.wine)
#   multiple instances = separate terminals, different prefixes:
#     ./wc3.sh ~/.wine ; ./wc3.sh ~/.wineGame1 ; ./wc3.sh ~/.wineGame2
set -u

# optional leading flag: --fullscreen / -f
while :; do case "${1:-}" in
  --fullscreen|-f) FULLSCREEN=1; shift ;;
  *) break ;;
esac; done

PREFIX="${1:-$HOME/.wine}"
HERE="$(cd "$(dirname "$0")" && pwd)"
VISION="$HERE/vision.py"
OK_TPL="$HERE/tpl/ok.png"
BTN_TPL="$HERE/tpl/btn.png"
EN_TPL="$HERE/tpl/enabled.png"

WC3='C:\Program Files (x86)\Warcraft III'
RES='1024x768'
WAR3_ARGS=(-opengl)
# FULLSCREEN=1 -> war3 runs native on main screen (no wine desktop wrapper).
# default 0    -> war3 runs inside the wine desktop window.
# MH always stays in the wine desktop (vision needs it). Set via env or --fullscreen flag.
FULLSCREEN="${FULLSCREEN:-0}"
# Input/automation is driven by SentinelFlow (attach to the wine desktop window
# and inject via xdotool --window); no in-prefix AutoClicker needed.
WIN_TIMEOUT=20          # secs to wait for MH window to appear
CLICK_TIMEOUT=20        # secs to find+click Start button
ENABLE_TIMEOUT=20       # secs to confirm "MH Enabled"

NAME=$(basename "$PREFIX")
DESK="$NAME - Wine Desktop"
[[ -e "$PREFIX/drive_c/Program Files (x86)/Warcraft III/Garena Universal MH.exe" ]] \
  || { echo "ERR: MH missing in $PREFIX" >&2; exit 1; }

find_win(){ xdotool search --name "$DESK" 2>/dev/null | head -1; }

cleanup(){
  echo; echo ">> Ctrl+C — killing $NAME"
  WINEPREFIX="$PREFIX" wineserver -k 2>/dev/null
  exit 0
}
trap cleanup INT TERM
fail(){ echo "ERR: $*" >&2; cleanup; }

echo ">> [$NAME] launch MH"
WINEPREFIX="$PREFIX" wine explorer "/desktop=$NAME,$RES" \
  "$WC3\\Garena Universal MH.exe" >"$PREFIX/mh.log" 2>&1 &

echo ">> [$NAME] wait for MH window"
end=$((SECONDS + WIN_TIMEOUT)); wid=""
while [[ $SECONDS -lt $end ]]; do wid=$(find_win); [[ -n $wid ]] && break; sleep 0.5; done
[[ -n $wid ]] || fail "MH window not found in ${WIN_TIMEOUT}s"
echo ">> [$NAME] MH window = $wid"

echo ">> [$NAME] dismiss info popup (OK)"
python3 "$VISION" click "$wid" "$OK_TPL" --timeout "$CLICK_TIMEOUT" \
  || fail "info popup OK not found/clicked"

echo ">> [$NAME] vision-click Start MapHack"
python3 "$VISION" click "$wid" "$BTN_TPL" --timeout "$CLICK_TIMEOUT" \
  || fail "Start button not found/clicked"

echo ">> [$NAME] confirm MH Enabled"
python3 "$VISION" wait "$wid" "$EN_TPL" --timeout "$ENABLE_TIMEOUT" \
  || fail "MH did not report Enabled"

if [[ "$FULLSCREEN" == 1 ]]; then
  echo ">> [$NAME] launch war3 FULLSCREEN on main screen"
  # no /desktop wrapper -> war3 renders natively; its own video pref (fullscreen) applies
  WINEPREFIX="$PREFIX" wine "$WC3\\war3.exe" "${WAR3_ARGS[@]}" \
    >"$PREFIX/war3.log" 2>&1 &
else
  echo ">> [$NAME] launch war3 in wine desktop"
  WINEPREFIX="$PREFIX" wine explorer "/desktop=$NAME,$RES" \
    "$WC3\\war3.exe" "${WAR3_ARGS[@]}" >"$PREFIX/war3.log" 2>&1 &
fi

echo ">> [$NAME] running. Ctrl+C to kill."
wait
