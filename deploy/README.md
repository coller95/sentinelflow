# wine-fleet harness

A generic, decoupled harness for launching capturable Wine app instances in
parallel. The launcher knows nothing about any specific game/app: all
app-specific knowledge lives in a per-app **PLUG** under `apps/<name>/`. The
reference app is `apps/wc3` (Warcraft III via Garena Master Host).

## Layout

```
deploy/
  fleet.sh               generic single-instance launcher
  netns.sh               same, inside a volatile netns+ipvlan for a distinct LAN IP
  vision.py              generic Xlib template-match click/wait helper
  lib/
    wine-capture.sh      generic DXVK d8vk + lavapipe DLL install into a prefix
  apps/
    wc3/                 reference PLUG
      profile.sh         sourced contract: paths, renderer, launch + vision sequence
      setup.sh           prefix prefs (calls lib/wine-capture.sh first)
      tpl/*.png          template images for vision.py
      README.md          reference app docs
```

The design is decoupled into three layers:

- **`fleet.sh`** is the generic launcher. It parses flags, builds a Wine
  desktop, applies window/workspace placement, and handles cleanup. It contains
  no app-specific logic.
- **`apps/<name>/profile.sh`** is the per-app plug. `fleet.sh` *sources* it and
  reads a small contract (see below) to learn what to launch and how.
- **`lib/wine-capture.sh`** and **`vision.py`** are shared building blocks that
  profiles call into (DLL install + on-screen template clicking).

## Usage

```sh
# generic single instance (host network):
./fleet.sh PROFILE PREFIX [--fullscreen|-f] [--workspace|-w N]

# same instance inside a volatile netns+ipvlan with its own LAN IP:
./netns.sh PROFILE PREFIX LAN_IP
```

- `PROFILE` is a path to an `apps/<name>/profile.sh` file.
- `PREFIX` is the `WINEPREFIX` directory for this instance.
- `--fullscreen` / `-f` launches the main exe natively (no Wine virtual desktop
  wrapper) for true fullscreen.
- `--workspace N` / `-w N` parks the instance window on GNOME workspace `N`.

`netns.sh` wraps the exact same `fleet.sh PROFILE PREFIX ...` invocation inside
a throwaway network namespace bridged to the LAN via ipvlan, so each instance
can present a distinct LAN IP (e.g. for games that bind one session per IP).

Example, using the reference app:

```sh
./fleet.sh apps/wc3/profile.sh ~/.wine-war3-1 --workspace 1
./netns.sh apps/wc3/profile.sh ~/.wine-war3-2 192.168.1.51
```

## Profile contract

`fleet.sh` sources the profile as a bash file. The profile **MUST** set:

| Variable   | Meaning                                                                 |
|------------|-------------------------------------------------------------------------|
| `APP_MAIN` | Windows path of the main exe, e.g. `'C:\\Program Files (x86)\\Warcraft III\\war3.exe'` |
| `APP_RES`  | Resolution string, e.g. `'1024x768'` (fleet defaults if unset)          |
| `APP_ENV`  | Bash array of `NAME=VALUE` env strings for the main launch (may be empty: `APP_ENV=()`) |
| `APP_ARGS` | Bash array of extra args for the main exe (may be empty: `APP_ARGS=()`)  |
| `APP_NAME` | Optional; fleet defaults to the basename of `PREFIX` if unset            |

The profile **MAY** define these functions (fleet detects them with
`declare -F`):

- **`app_check_prefix`** — preflight. `$PREFIX` is in the environment. Print an
  `ERR` line and `return` nonzero if required files are missing.
- **`app_launch_helper`** — launch a helper app that OWNS the Wine desktop (e.g.
  Garena Master Host) into `wine explorer "/desktop=$NAME,$RES"`. If defined,
  fleet waits for the desktop window, runs `app_pre_main`, then launches
  `APP_MAIN` into the **same** desktop (the helper injects into it). If **not**
  defined, fleet launches `APP_MAIN` directly into a fresh Wine desktop.
  `$PREFIX`, `$NAME`, `$RES` are in the environment.
- **`app_pre_main`** — `$1` is the desktop window id (`wid`); runs the
  vision/click sequence. Default is a no-op.

Environment and flags that fleet provides to the profile (and uses itself):

- `PREFIX`, `NAME`, `DESK` (`"$NAME - Wine Desktop"`), `RES`, `FULLSCREEN`,
  `WORKSPACE`.
- Flags: `[--fullscreen|-f] [--workspace|-w N]`, then positional `PROFILE PREFIX`.
- The `RENDERER` env (`dxvk` default, or `opengl`) is a **profile concern**, not
  a `fleet.sh` concern: the profile reads `RENDERER` and computes `APP_ENV` /
  `APP_ARGS` accordingly.

## Adding a new app

1. Create `apps/<name>/profile.sh` setting `APP_MAIN`, `APP_RES`, `APP_ENV`,
   `APP_ARGS` and (optionally) the `app_*` functions above.
2. Create `apps/<name>/setup.sh` that calls `lib/wine-capture.sh` to install the
   capturable D3D8/9 present path (DXVK d8vk + lavapipe), then applies any
   prefix-specific prefs.
3. Drop any template images for `app_pre_main` under `apps/<name>/tpl/` and click
   them via `vision.py`.
4. Run `./fleet.sh apps/<name>/profile.sh <prefix>`.

See **`apps/wc3/README.md`** for the reference implementation.
