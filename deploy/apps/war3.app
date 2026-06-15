# war3.app — Warcraft III: The Frozen Throne launch profile.
# Sourced by deploy/modules/profiles.sh on `-a war3` (or `-a wc3`).
# Sets the harness launch globals; see deploy/CLAUDE.md "App profiles".
APP='C:\Program Files (x86)\Warcraft III\Frozen Throne.exe'
APP_ARGS='-window -opengl'   # windowed + GL renderer (launcher hangs without it)
NO_DESKTOP=1                 # own game window, not a wine virtual desktop
WIN_TITLE='Warcraft III'     # wait-for / attach / node-seed by the game's title
HOLD_PROC='war3.exe'         # persistent engine; the Frozen Throne.exe launcher exits
PROFILE_COUNT=1              # default instance count (user -c overrides)

# Optional install hook for `bootstrap.sh --app war3 <prefix>`. WC3's installer
# is interactive (GUI + CD key) with no silent mode, so this does not auto-install
# — it points at the reproducible snapshot path and the manual steps.
app_install(){
  cat <<'MSG'
>> Warcraft III install is interactive (GUI + CD key) — no silent install.
   Reproducible path — snapshot a ready prefix instead of installing:
     ./deploy/bootstrap.sh --save  ~/.wine war3-prefix.tar.zst   # on a box that has WC3
     ./deploy/bootstrap.sh --restore war3-prefix.tar.zst ~/.wineNew
   Manual install (needs the discs):
     1. mount the WC3 ISOs, run the installer with WINEPREFIX=<this prefix>
     2. enter the CD key from ~/wc3/war3.txt
     3. run War3TFT_126a_English.exe to patch to 1.26a
MSG
}
