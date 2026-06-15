# war3.app — Warcraft III: The Frozen Throne launch profile.
# Sourced by deploy/modules/profiles.sh on `-a war3` (or `-a wc3`).
# Sets the harness launch globals; see deploy/CLAUDE.md "App profiles".
APP='C:\Program Files (x86)\Warcraft III\Frozen Throne.exe'
APP_ARGS='-window -opengl'   # windowed + GL renderer (launcher hangs without it)
NO_DESKTOP=1                 # own game window, not a wine virtual desktop
WIN_TITLE='Warcraft III'     # wait-for / attach / node-seed by the game's title
HOLD_PROC='war3.exe'         # persistent engine; the Frozen Throne.exe launcher exits
PROFILE_COUNT=1              # default instance count (user -c overrides)
