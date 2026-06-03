# wine-fleet harness

Launch capturable Wine app instances in parallel. The launcher knows nothing
about any specific game/app: all app-specific knowledge lives in a per-app plug
under `apps/<name>/`. Reference app: `apps/wc3` (Warcraft III + Garena MH).

## Layout

```
deploy/
  bootstrap.sh         SETUP: new-machine deps (apt) + fresh wow64 prefix + DXVK
  launch.sh            ENTRY: launch one instance (host network)
  launch-netns.sh      ENTRY: launch one instance with its own LAN IP (netns+ipvlan)
  vision.py            helper: Xlib template-match click/wait against a window
  lib/                 generic, app-agnostic building blocks
    window.sh            place/park X windows (find / wait / move-to-workspace)
    wine.sh              spawn APP_MAIN under wine (native | virtual desktop)
    capture.sh           install DXVK d8vk DLLs so D3D8/9 presents a capturable frame
  apps/
    wc3/               reference plug (Warcraft III)
      config.sh          tells launch.sh WHAT + HOW to launch war3 (the contract)
      setup.sh           provision a prefix ONCE (prefs + calls lib/capture.sh)
      maphack.sh         OPTIONAL, standalone: inject + enable Garena MH
      tpl/*.png          template images for vision.py (maphack uses these)
      README.md          reference-app docs
```

Roles, plainly:

- **`launch.sh`** — the entrypoint/sequencer. Parses flags, sources the app
  `config.sh` + the libs, then: preflight → spawn APP_MAIN → wait/park window.
  No app-specific logic.
- **`lib/window.sh`, `lib/wine.sh`** — the two single-job steps `launch.sh`
  calls: window placement, and wine spawning. `launch.sh` just sequences them.
- **`apps/<name>/config.sh`** — the per-app plug. `launch.sh` *sources* it to
  learn what to run and with what env (see contract below).
- **`lib/capture.sh`, `vision.py`** — shared tools an app's `setup.sh` /
  `maphack.sh` call into (DLL install + on-screen template clicking).

## Setup (new machine / new prefix)

```sh
# installs missing system deps (wine ≥9.0, winetricks, xdotool, scrot,
# mesa lavapipe, python vision libs, iproute2, xvfb) then makes a fresh
# wow64 prefix + DXVK. Idempotent — re-runs skip apt when deps are present.
./bootstrap.sh ~/.wine-war3-1
```

Then provision the prefix for an app once (`apps/<name>/setup.sh`), and launch.

## Usage

```sh
# one instance, host network:
./launch.sh apps/wc3/config.sh ~/.wine-war3-1 [--fullscreen|-f] [--workspace|-w N]

# one instance with its own LAN IP (volatile netns + ipvlan):
./launch-netns.sh apps/wc3/config.sh ~/.wine-war3-2 192.168.1.51
```

- `CONFIG` = path to an `apps/<name>/config.sh`.
- `PREFIX` = the `WINEPREFIX` directory for this instance.
- `--fullscreen` / `-f` runs the exe native (no Wine virtual desktop) for true fullscreen.
- `--workspace N` / `-w N` parks the window on GNOME workspace `N`.

`launch-netns.sh` wraps the same `launch.sh CONFIG PREFIX ...` call inside a
throwaway network namespace bridged to the LAN via ipvlan, so each instance can
present a distinct LAN IP (for games that bind one session per IP).

## Config contract

`launch.sh` sources `config.sh` as bash. It **MUST** set:

| Variable   | Meaning                                                                 |
|------------|-------------------------------------------------------------------------|
| `APP_MAIN` | Windows path of the main exe, e.g. `'C:\\Program Files (x86)\\Warcraft III\\war3.exe'` |
| `APP_ENV`  | Bash array of `NAME=VALUE` env for the launch (may be empty: `APP_ENV=()`) |
| `APP_ARGS` | Bash array of extra args for the exe (may be empty: `APP_ARGS=()`)       |
| `APP_RES`  | Resolution string, e.g. `'1024x768'` (defaults to `1024x768` if unset)  |
| `APP_NAME` | Optional instance name (defaults to the basename of `PREFIX`)           |

It **MAY** define one function (detected with `declare -F`):

- **`app_check_prefix`** — preflight. `$PREFIX` is in the env. Print an `ERR`
  line and `return` nonzero if required files are missing.

`launch.sh` exports to the config: `PREFIX NAME DESK RES FULLSCREEN WORKSPACE`.

## Maphack (wc3, optional)

Maphack is **decoupled** from launch — its own script, not a config hook. It
starts Garena Universal MH into the wine desktop and clicks through its enable
dialog (`vision.py` + `tpl/*.png`). Run it FIRST so a war3 launched into the same
desktop gets injected:

```sh
./apps/wc3/maphack.sh ~/.wine-war3-1            # owns the desktop, enables MH
./launch.sh apps/wc3/config.sh ~/.wine-war3-1   # war3 joins the same desktop
```

Skip `maphack.sh` for a clean (no-maphack) launch.

## Adding a new app

1. `apps/<name>/config.sh` — set `APP_MAIN`, `APP_ENV`, `APP_ARGS` (+ optional
   `APP_RES` / `APP_NAME` / `app_check_prefix`).
2. `apps/<name>/setup.sh` — call `lib/capture.sh` for the capturable D3D8/9
   present path, then apply any prefix prefs.
3. Run `./launch.sh apps/<name>/config.sh <prefix>`.

See **`apps/wc3/README.md`** for the reference implementation.
