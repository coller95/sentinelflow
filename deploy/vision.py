#!/usr/bin/env python3
"""Event-based vision helper for the MH launch flow.

Captures a single X window's pixels via Xlib (works under XWayland where
full-screen grabs return black), template-matches, and reports/acts.

Usage:
  vision.py click  <WID> <template.png> [--conf 0.8] [--timeout 20]
      poll the window until template appears, then click its center. exit 0.
  vision.py wait   <WID> <template.png> [--conf 0.8] [--timeout 20]
      poll until template appears. exit 0 when seen (no click).

WID = X window id (decimal or 0x hex), e.g. from `xdotool search --name`.
Exit non-zero on timeout.
"""
import sys, time, subprocess, argparse
import numpy as np, cv2
from Xlib import X, display


def grab(dpy, win):
    """Return the window's current pixels as a BGR numpy array."""
    g = win.get_geometry()
    w, h = g.width, g.height
    raw = win.get_image(0, 0, w, h, X.ZPixmap, 0xffffffff)
    buf = np.frombuffer(raw.data, dtype=np.uint8)
    # XWayland windows are 32-bit padded: BGRX. Fall back to 24-bit if needed.
    if buf.size == w * h * 4:
        return buf.reshape(h, w, 4)[:, :, :3].copy()
    if buf.size == w * h * 3:
        return buf.reshape(h, w, 3).copy()
    raise RuntimeError(f"unexpected image bytes {buf.size} for {w}x{h}")


def locate(img, tpl, conf):
    res = cv2.matchTemplate(img, tpl, cv2.TM_CCOEFF_NORMED)
    _, maxv, _, maxloc = cv2.minMaxLoc(res)
    if maxv < conf:
        return None, maxv
    th, tw = tpl.shape[:2]
    return (maxloc[0] + tw // 2, maxloc[1] + th // 2), maxv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["click", "wait"])
    ap.add_argument("wid")
    ap.add_argument("template")
    ap.add_argument("--conf", type=float, default=0.80)
    ap.add_argument("--timeout", type=float, default=20)
    ap.add_argument("--poll", type=float, default=0.5)
    a = ap.parse_args()

    wid = int(a.wid, 0)
    tpl = cv2.imread(a.template)
    if tpl is None:
        print(f"ERR: cannot read template {a.template}", file=sys.stderr); sys.exit(2)

    dpy = display.Display()
    win = dpy.create_resource_object("window", wid)

    deadline = time.time() + a.timeout
    best = 0.0
    while time.time() < deadline:
        try:
            img = grab(dpy, win)
        except Exception as e:
            print(f"grab failed: {e}", file=sys.stderr); time.sleep(a.poll); continue
        pt, v = locate(img, tpl, a.conf)
        best = max(best, v)
        if pt:
            x, y = pt
            print(f"matched conf={v:.3f} at {x},{y}")
            if a.action == "click":
                subprocess.run(["xdotool", "mousemove", "--window", str(wid),
                                str(x), str(y), "click", "1"])
            sys.exit(0)
        time.sleep(a.poll)

    print(f"ERR: timeout, best conf={best:.3f} (< {a.conf})", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
