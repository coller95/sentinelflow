# apps/wc3 — Warcraft III + Garena MH

Reference plug that brings up one or many Warcraft III (Frozen Throne 1.26)
instances under Wine — optionally with Garena Universal MH — ready for
SentinelFlow to attach, capture, and drive.

All commands below run **from `deploy/`** (the launcher root). The plug provides
config + scripts; the generic `launch.sh` / `launch-netns.sh` do the launching.

## Layout

| Path | Role |
|------|------|
| `apps/wc3/setup.sh` | **Run once per prefix.** Installs DXVK d8vk DLLs (via `lib/capture.sh`) + seeds windowed video config so war3 renders a *capturable* frame and reaches its menu. See "Capture: the GL-black fix" below. |
| `apps/wc3/config.sh` | The launch contract `launch.sh` sources: `APP_MAIN` (war3), `APP_ENV` (DXVK/lavapipe present env), `app_check_prefix`. Pure war3 launch — **no** maphack. |
| `apps/wc3/maphack.sh` | **Optional, standalone.** Starts Garena MH into the wine desktop and clicks through its enable dialog (vision). Run BEFORE `launch.sh` so war3 joins the same desktop and gets injected. |
| `apps/wc3/tpl/` | Templates for the maphack flow: `ok.png` (info popup), `btn.png` (Start MapHack), `enabled.png` (MH Enabled). |
| `../../vision.py` (`deploy/vision.py`) | **Generic** Xlib template-match helper (`click` / `wait` against a window id). `maphack.sh` calls it. |
| `../../lib/capture.sh` (`deploy/lib/capture.sh`) | DLL install + capture-prep logic shared by app setups; invoked by `apps/wc3/setup.sh`. |

Input/automation is **SentinelFlow's job** — attach to the wine desktop window
and inject via `xdotool --window`. There is no in-prefix AutoClicker.

## Prerequisites

- Wine **≥9.0** (needs the wow64 single-arch prefix — no 32-bit multilib
  required; staging optional, only adds fsync/esync perf) with a prefix
  containing WC3 + `Garena Universal MH.exe`
- `xdotool`, `python3` with `numpy`, `opencv`, `python-xlib` (the SentinelFlow
  `.venv` has these)
- An X display: `:0` (real GPU) or a per-instance
  `Xvfb :N -screen 0 1024x768x24` (headless)
- For capturable war3 (see "Capture: the GL-black fix"): a DXVK build with
  **d8vk** (`d3d8.dll`, e.g. Lutris' DXVK runtime or `DXVK_X32_DIR=...`) and a
  **lavapipe** Vulkan ICD (`/usr/share/vulkan/icd.d/lvp_icd.json`, mesa software
  Vulkan). `setup.sh` (through `lib/capture.sh`) installs the DLLs into the
  prefix.

## Run one instance

```bash
./apps/wc3/setup.sh ~/.wineGame1                          # ONCE per prefix (DXVK + video config)
./apps/wc3/maphack.sh ~/.wineGame1                        # OPTIONAL: enable MH first (own desktop)
./launch.sh apps/wc3/config.sh ~/.wineGame1               # war3 in a wine desktop window
./launch.sh --fullscreen apps/wc3/config.sh ~/.wineGame1  # war3 native fullscreen on the main screen
./launch.sh --workspace 2 apps/wc3/config.sh ~/.wineGame1 # park this instance on GNOME workspace 2
```

Skip the `maphack.sh` line for a clean (no-maphack) launch.

`--fullscreen` and `--workspace N` are runner flags and must come **before** the
positional arguments (`config.sh` and the prefix).

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

`launch-netns.sh` wraps a profile in a volatile network namespace + ipvlan so each
instance gets its own LAN IP (multi-box on one host). Everything is torn down on
exit.

```bash
./launch-netns.sh apps/wc3/config.sh ~/.wine       192.168.1.150
./launch-netns.sh apps/wc3/config.sh ~/.wineGame1  192.168.1.151
./launch-netns.sh apps/wc3/config.sh ~/.wineGame2  192.168.1.152
```

Edit the LAN block at the top of `launch-netns.sh` (`PARENT`, `GATEWAY`, `CIDR`, `DNS`)
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
- **Fix (what `setup.sh` + `config.sh` do).** Route war3's D3D8 through **DXVK
  d8vk on Mesa lavapipe** (software Vulkan). The DLL install lives in
  `lib/capture.sh`, called by `setup.sh`; `config.sh`'s `APP_ENV` points the
  Vulkan ICD at lavapipe (`LVP_ICD`). Mesa's X11 software WSI copies every Present
  into the window pixmap via `xcb_put_image`/MIT-SHM, so the existing capturer
  reads real pixels **with no code change** — same recipe on a real-GPU host *or*
  bare headless `Xvfb` (the failure was the present path, not the absence of a
  GPU). Verified live: the full WC3 menu captures in color and SentinelFlow
  clicks register. **Never** use a direct-GPU/DRI3 path for a capturable
  instance — it reads black.
- **640×480 stall** is a *separate* first-run issue (no `War3Preferences.txt` /
  `Video` registry → war3 sits at its splash size). `setup.sh` seeds both and
  moves the intro `Movies` aside so war3 advances to the menu.

For bare-`Xvfb` fleet nodes, create the display at 24-bit depth:

```bash
Xvfb :N -screen 0 1024x768x24 +extension COMPOSITE +extension DAMAGE
```

then the same `setup.sh` + `config.sh` applies. Cap CPU contention across many
software-rendered instances if needed. The maphack enable flow is GDI and always
capturable regardless of renderer.
