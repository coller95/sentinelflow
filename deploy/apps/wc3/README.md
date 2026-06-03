# apps/wc3 — Warcraft III + Garena MH app profile

Proven app profile that brings up one or many Warcraft III (Frozen Throne 1.26)
+ Garena Universal MH instances under Wine, ready for SentinelFlow to attach,
capture, and drive. This is the reference profile for the Linux/X11/Wine fleet.

All commands below are run **from `deploy/`** (the repo's launcher root). The
profile plugs into the generic `fleet.sh` / `netns.sh` runners — it does not
ship its own launcher.

## Layout

| Path | Role |
|------|------|
| `apps/wc3/setup.sh` | **Run once per prefix.** Installs DXVK d8vk DLLs (via `lib/wine-capture.sh`) + seeds windowed video config so war3 renders a *capturable* frame and reaches its menu. See "Capture: the GL-black fix" below. |
| `apps/wc3/profile.sh` | The WC3 app profile consumed by the runners. Defines the MH launch + vision-confirm flow, then launches war3 in the same prefix (MH injects into it). Sets `APP_MAIN` (war3), `APP_ENV` (renderer/present env), and `app_launch_helper` (the MH enable sequence). |
| `apps/wc3/tpl/` | Templates for the MH flow: `ok.png` (info popup), `btn.png` (Start MapHack), `enabled.png` (MH Enabled). |
| `../../vision.py` (`deploy/vision.py`) | **Generic** Xlib template-match helper (`click` / `wait` against a window id). The profile calls it for the MH launch sequence; it is no longer WC3-specific. |
| `../../lib/wine-capture.sh` (`deploy/lib/wine-capture.sh`) | DLL install + capture-prep logic shared by app setups; invoked by `apps/wc3/setup.sh`. |

Input/automation is **SentinelFlow's job** — attach to the wine desktop window
and inject via `xdotool --window`. There is no in-prefix AutoClicker.

## Prerequisites

- Wine (tested: wine-staging 11.9) with a prefix containing WC3 +
  `Garena Universal MH.exe`
- `xdotool`, `python3` with `numpy`, `opencv`, `python-xlib` (the SentinelFlow
  `.venv` has these)
- An X display: `:0` (real GPU) or a per-instance
  `Xvfb :N -screen 0 1024x768x24` (headless)
- For capturable war3 (see "Capture: the GL-black fix"): a DXVK build with
  **d8vk** (`d3d8.dll`, e.g. Lutris' DXVK runtime or `DXVK_X32_DIR=...`) and a
  **lavapipe** Vulkan ICD (`/usr/share/vulkan/icd.d/lvp_icd.json`, mesa software
  Vulkan). `setup.sh` (through `lib/wine-capture.sh`) installs the DLLs into the
  prefix.

## Run one instance

```bash
./apps/wc3/setup.sh ~/.wineGame1                          # ONCE per prefix (DXVK + video config)
./fleet.sh apps/wc3/profile.sh ~/.wineGame1               # in a wine desktop window
./fleet.sh --fullscreen apps/wc3/profile.sh ~/.wineGame1  # war3 native fullscreen on the main screen
./fleet.sh --workspace 2 apps/wc3/profile.sh ~/.wineGame1 # park this instance on GNOME workspace 2
```

`--fullscreen` and `--workspace N` are runner flags and must come **before** the
positional arguments (`profile.sh` and the prefix).

`--workspace N` (0-indexed) moves the instance's window to its own GNOME/EWMH
workspace after it appears. Capture (`get_image`) and input
(`xdotool --window`) are workspace-independent — mutter keeps off-workspace
windows composited — so you can watch one workspace by eye while the fleet runs
on others. Needs an EWMH-aware WM (GNOME/mutter); ignored with a warning on a
bare Xvfb (no WM). For fixed slots:

```bash
gsettings set org.gnome.mutter dynamic-workspaces false
gsettings set org.gnome.desktop.wm.preferences num-workspaces 6
```

## Run a fleet (one per prefix, distinct LAN IPs)

`netns.sh` wraps a profile in a volatile network namespace + ipvlan so each
instance gets its own LAN IP (multi-box on one host). Everything is torn down on
exit.

```bash
./netns.sh apps/wc3/profile.sh ~/.wine       192.168.1.150
./netns.sh apps/wc3/profile.sh ~/.wineGame1  192.168.1.151
./netns.sh apps/wc3/profile.sh ~/.wineGame2  192.168.1.152
```

Edit the LAN block at the top of `netns.sh` (`PARENT`, `GATEWAY`, `CIDR`, `DNS`)
to match the host network. Runner flags (`--fullscreen`, `--workspace N`) go
before the positionals here too.

## How SentinelFlow attaches

Each instance creates a window named `<prefix-basename> - Wine Desktop`
(e.g. `wineGame1 - Wine Desktop`). Point a SentinelFlow cluster node at that
title via `/api/app/attach` (window_title), then capture/condition/trigger as
usual. Input is injected window-targeted, so instances don't steal focus from
each other.

## Capture: the GL-black fix (DXVK + lavapipe)

SentinelFlow captures window pixels via Xlib `get_image`, which reads the
**server-side window pixmap**. The problem and the fix:

- **Root cause.** war3's Direct3D8/OpenGL frame, when rendered directly on the
  GPU (DRI3/Present) *or* via indirect GLX, lives in a GPU/dmabuf buffer that is
  flipped to screen **out-of-band** — it never enters the X window pixmap. So
  `get_image` *and* `scrot` read **pure black**, while GDI windows (MH, dialogs,
  the wine desktop wrapper) capture fine because GDI draws into the pixmap.
- **Fix (what `setup.sh` + `RENDERER=dxvk` do).** Route war3's D3D8 through
  **DXVK d8vk on Mesa lavapipe** (software Vulkan). The DLL install lives in
  `lib/wine-capture.sh`, called by `setup.sh`. Mesa's X11 software WSI copies
  every Present into the window pixmap via `xcb_put_image`/MIT-SHM, so the
  existing capturer reads real pixels **with no code change** — same recipe on a
  real-GPU host *or* bare headless `Xvfb` (the failure was the present path, not
  the absence of a GPU). Verified live: the full WC3 menu captures in color and
  SentinelFlow clicks register.
- **640×480 stall** is a *separate* first-run issue (no `War3Preferences.txt` /
  `Video` registry → war3 sits at its splash size). `setup.sh` seeds both and
  moves the intro `Movies` aside so war3 advances to the menu.

`RENDERER` (env): `dxvk` (default, capturable) or `opengl` (fallback — forces
the llvmpipe `drisw` `XPutImage` path with `LIBGL_DRI3_DISABLE=1`). **Never** use
a direct-GPU/DRI3 path for a capturable instance — it reads black.

For bare-`Xvfb` fleet nodes, create the display at 24-bit depth:

```bash
Xvfb :N -screen 0 1024x768x24 +extension COMPOSITE +extension DAMAGE
```

then the same `setup.sh` + `RENDERER=dxvk` applies. Cap CPU contention across
many software-rendered instances if needed. The MH enable flow is GDI and always
capturable regardless of renderer.
