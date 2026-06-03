#!/usr/bin/env bash
# apps/wc3/maphack.sh — start Garena Universal MH into a war3 wine desktop and
# click through its enable dialog (vision). SEPARATE from launch: maphack owns
# the wine desktop "$NAME - Wine Desktop"; a war3 launched LATER into the same
# /desktop=$NAME,$RES (via launch.sh) gets injected. Skip this for a clean launch.
#
# Usage:  ./maphack.sh <PREFIX> [NAME] [RES]
#   PREFIX = wine prefix path (e.g. ~/.wineGame1)
#   NAME   = desktop/instance name (default: basename of PREFIX)
#   RES    = resolution           (default: 1024x768)
#
# Then, in another terminal, launch war3 into the SAME desktop:
#   ./launch.sh apps/wc3/config.sh <PREFIX>
set -u

PREFIX="${1:?need PREFIX (e.g. ~/.wineGame1)}"
NAME="${2:-$(basename "$PREFIX")}"
RES="${3:-1024x768}"
DESK="$NAME - Wine Desktop"
WC3='C:\Program Files (x86)\Warcraft III'

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VISION="$HERE/../../vision.py"
TPL="$HERE/tpl"
WIN_TIMEOUT=20
CLICK_TIMEOUT=20
ENABLE_TIMEOUT=20

mh="$PREFIX/drive_c/Program Files (x86)/Warcraft III/Garena Universal MH.exe"
[[ -f "$mh" ]] || { echo "ERR: missing Garena Universal MH.exe: $mh" >&2; exit 1; }

echo ">> [$NAME] launch maphack into wine desktop $NAME,$RES"
WINEPREFIX="$PREFIX" wine explorer "/desktop=$NAME,$RES" \
  "$WC3\\Garena Universal MH.exe" >"$PREFIX/mh.log" 2>&1 &

echo ">> [$NAME] wait for wine desktop window"
end=$((SECONDS + WIN_TIMEOUT)); wid=""
while [[ $SECONDS -lt $end ]]; do
  wid=$(xdotool search --name "$DESK" 2>/dev/null | head -1)
  [[ -n $wid ]] && break; sleep 0.5
done
[[ -n $wid ]] || { echo "ERR: wine desktop window not found in ${WIN_TIMEOUT}s" >&2; exit 1; }

echo ">> [$NAME] enable maphack (vision)"
python3 "$VISION" click "$wid" "$TPL/ok.png"      --timeout "$CLICK_TIMEOUT"  || exit 1
python3 "$VISION" click "$wid" "$TPL/btn.png"     --timeout "$CLICK_TIMEOUT"  || exit 1
python3 "$VISION" wait  "$wid" "$TPL/enabled.png" --timeout "$ENABLE_TIMEOUT" || exit 1
echo ">> [$NAME] maphack enabled. Now launch war3 into the same desktop:"
echo "   ./launch.sh apps/wc3/config.sh $PREFIX"
