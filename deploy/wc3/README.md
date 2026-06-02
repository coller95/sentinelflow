# deploy/wc3 — Warcraft III + Garena MH launch tooling

Proven scripts that bring up one or many Warcraft III (Frozen Throne 1.26) +
Garena Universal MH instances under Wine, ready for SentinelFlow to attach,
capture, and drive. This is the reference launcher for the Linux/X11/Wine fleet.

## Files

| File | Role |
|------|------|
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
- An X display (`:0` real GPU, or a per-instance `Xvfb :N` for headless — see caveat)

## Run one instance

```bash
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

## Capture caveat (important for headless)

SentinelFlow captures window pixels via Xlib `get_image`. This reads
**server-side** pixels:

- **GDI windows** (the MH GUI, normal Win32 dialogs) capture correctly.
- **war3's 3D OpenGL surface** only lands in the window pixmap when GL can
  present to it. On a host with a real GPU + DRI3 this works. Under bare `Xvfb`
  (software `llvmpipe`, no DRI3) the war3 surface reads back **black** — even a
  full screen-grab (`scrot`) reads black, because the pixels never reach the X
  server. Symptom in the war3 log: `libEGL warning: DRI3 error: Could not get
  DRI3 device`.

So: watch the **Wine desktop window** (it composites GDI content), and for the
3D game view ensure a GL path that presents to the window (real GPU/DRI3), or
use an in-Wine capture. The MH enable flow in `wc3.sh` is GDI and always
capturable.
