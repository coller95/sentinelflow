# deploy/wc3 — Warcraft III + Garena MH launch tooling

Proven scripts that bring up one or many Warcraft III (Frozen Throne 1.26) +
Garena Universal MH instances under Wine, ready for SentinelFlow to attach,
capture, and drive. This is the reference launcher for the Linux/X11/Wine fleet.

## Files

| File | Role |
|------|------|
| `setup-prefix.sh` | **Run once per prefix.** Installs DXVK d8vk DLLs + seeds windowed video config so war3 renders a *capturable* frame and reaches its menu. See "Capture: the GL-black fix" below. |
| `wc3.sh` | Launch ONE instance: start MH in a Wine desktop, vision-click through its enable flow, then launch war3 in the same prefix (MH injects into it). Blocks until Ctrl+C, then kills the prefix. |
| `play.sh` | Wrap `wc3.sh` in a volatile network namespace + ipvlan so the instance gets its own LAN IP (multi-box on one host). Everything is torn down on exit. |
| `vision.py` | Standalone Xlib template-match helper used by `wc3.sh` for the MH launch sequence (`click` / `wait` against a window id). |
| `tpl/` | Templates for the MH flow: `ok.png` (info popup), `btn.png` (Start MapHack), `enabled.png` (MH Enabled). |

AutoClicker is **gone** — input/automation is now SentinelFlow's job (attach to
the wine desktop window, inject via `xdotool --window`). The old in-prefix
AutoClicker.exe is no longer launched or shipped.

## Prerequisites

- Wine (tested: wine-staging 11.9) with a prefix containing WC3 + `Garena Universal MH.exe`
- `xdotool`, `python3` with `numpy`, `opencv`, `python-xlib` (the SentinelFlow `.venv` has these)
- An X display: `:0` (real GPU) or a per-instance `Xvfb :N -screen 0 1024x768x24` (headless)
- For capturable war3 (see "Capture: the GL-black fix"): a DXVK build with **d8vk**
  (`d3d8.dll`, e.g. Lutris' DXVK runtime or `DXVK_X32_DIR=...`) and a **lavapipe**
  Vulkan ICD (`/usr/share/vulkan/icd.d/lvp_icd.json`, mesa software Vulkan)

## Run one instance

```bash
./setup-prefix.sh ~/.wineGame1        # ONCE per prefix (DXVK + video config)
./wc3.sh ~/.wineGame1                 # in a wine desktop window
./wc3.sh --fullscreen ~/.wineGame1    # war3 native fullscreen on the main screen
./wc3.sh --workspace 2 ~/.wineGame1   # park this instance on GNOME workspace 2
```

`--workspace N` (or `WORKSPACE=N`, 0-indexed) moves the instance's window to its
own GNOME/EWMH workspace after it appears. Capture (`get_image`) and input
(`xdotool --window`) are workspace-independent — mutter keeps off-workspace
windows composited — so you can watch one workspace by eye while the fleet runs
on others. Needs an EWMH-aware WM (GNOME/mutter); ignored with a warning on a
bare Xvfb (no WM). For fixed slots: `gsettings set org.gnome.mutter
dynamic-workspaces false && gsettings set
org.gnome.desktop.wm.preferences num-workspaces 6`.

## Run a fleet (one per prefix, distinct LAN IPs, own workspaces)

```bash
WORKSPACE=0 ./play.sh ~/.wine       192.168.1.150
WORKSPACE=1 ./play.sh ~/.wineGame1  192.168.1.151
WORKSPACE=2 ./play.sh ~/.wineGame2  192.168.1.152
```

(`play.sh` passes the environment through to `wc3.sh`, so `WORKSPACE` works there too.)

Edit the LAN block at the top of `play.sh` (`PARENT`, `GATEWAY`, `CIDR`, `DNS`)
to match the host network.

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
- **Fix (what `setup-prefix.sh` + `RENDERER=dxvk` do).** Route war3's D3D8
  through **DXVK d8vk on Mesa lavapipe** (software Vulkan). Mesa's X11 software
  WSI copies every Present into the window pixmap via `xcb_put_image`/MIT-SHM, so
  the existing capturer reads real pixels **with no code change** — same recipe
  on a real-GPU host *or* bare headless `Xvfb` (the failure was the present path,
  not the absence of a GPU). Verified live: the full WC3 menu captures in color
  and SentinelFlow clicks register.
- **640×480 stall** is a *separate* first-run issue (no `War3Preferences.txt` /
  `Video` registry → war3 sits at its splash size). `setup-prefix.sh` seeds both
  and moves the intro `Movies` aside so war3 advances to the menu.

`RENDERER` (env): `dxvk` (default, capturable) or `opengl` (fallback — forces the
llvmpipe `drisw` `XPutImage` path with `LIBGL_DRI3_DISABLE=1`). **Never** use a
direct-GPU/DRI3 path for a capturable instance — it reads black.

For bare-`Xvfb` fleet nodes, create the display at 24-bit depth:
`Xvfb :N -screen 0 1024x768x24 +extension COMPOSITE +extension DAMAGE`, then the
same `setup-prefix.sh` + `RENDERER=dxvk` applies. Cap CPU contention across many
software-rendered instances if needed. The MH enable flow is GDI and always
capturable regardless of renderer.
