import os
import re
import shlex
import signal
import subprocess
import time
from pathlib import Path
from typing import Any, List, Optional

import cv2
import numpy as np

from Src.domain.interfaces import IWindowManager, IScreenCapturer, IInputController

# File-local type aliases (X11 / Linux flavour of the OS handler).
XWindow = int           # X11 Window ID (XID)
PID = int
Keysym = str            # xdotool keysym name, e.g. "Return", "space", "a"
NormalizedCoord = float

# Named keys -> xdotool keysym. Single visible chars pass through directly.
_KEY_NAME_TO_KEYSYM: dict[str, str] = {
    "enter": "Return", "return": "Return",
    "tab": "Tab", "escape": "Escape", "esc": "Escape",
    "space": "space", "spacebar": "space",
    "backspace": "BackSpace", "delete": "Delete", "del": "Delete",
    "insert": "Insert", "home": "Home", "end": "End",
    "pageup": "Prior", "pagedown": "Next",
    "left": "Left", "right": "Right", "up": "Up", "down": "Down",
    "arrowleft": "Left", "arrowright": "Right", "arrowup": "Up", "arrowdown": "Down",
    "lctrl": "Control_L", "rctrl": "Control_R",
    "lshift": "Shift_L", "rshift": "Shift_R",
    "lalt": "Alt_L", "ralt": "Alt_R",
    "numlock": "Num_Lock",
    "numpad0": "KP_0", "numpad1": "KP_1", "numpad2": "KP_2", "numpad3": "KP_3",
    "numpad4": "KP_4", "numpad5": "KP_5", "numpad6": "KP_6", "numpad7": "KP_7",
    "numpad8": "KP_8", "numpad9": "KP_9",
    "numpadadd": "KP_Add", "numpadsubtract": "KP_Subtract",
    "numpadmultiply": "KP_Multiply", "numpaddivide": "KP_Divide",
    "numpaddecimal": "KP_Decimal", "numpadenter": "KP_Enter",
}


def _run(argv: List[str]) -> Optional[str]:
    """Run a command, return stdout stripped, or None if it failed."""
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=10)
    except Exception:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


class LinuxWindowManager(IWindowManager):
    def find_window_by_title(self, title: str):
        out = _run(["xdotool", "search", "--name", f"^{re.escape(title)}$"])
        if not out:
            return None
        try:
            return int(out.splitlines()[0])
        except (ValueError, IndexError):
            return None

    def find_window_by_pid(self, pid: PID):
        out = _run(["xdotool", "search", "--pid", str(pid)])
        if not out:
            return None
        try:
            return int(out.splitlines()[0])
        except (ValueError, IndexError):
            return None

    def find_pid_by_window(self, handle: XWindow):
        out = _run(["xdotool", "getwindowpid", str(int(handle))])
        if out is None:
            raise RuntimeError(f"No PID for window {handle}")
        try:
            return int(out)
        except ValueError:
            raise RuntimeError(f"Bad PID for window {handle}: {out!r}")

    def launch_process(self, executable_path: str):
        command = executable_path.strip()
        if not command:
            raise ValueError("Executable path cannot be empty.")

        # Native ELF / script with an executable bit -> argv form (no shell).
        # Everything else (e.g. "wine /path/Game.exe", shell builtins) -> shell.
        try:
            argv = shlex.split(command, posix=True)
        except ValueError:
            argv = [command]

        exe = Path(argv[0]) if argv else Path(command)
        if exe.exists() and os.access(str(exe), os.X_OK):
            process = subprocess.Popen(argv, shell=False)
        else:
            process = subprocess.Popen(command, shell=True)

        time.sleep(1.5)  # allow the window to appear
        return process.pid

    def terminate_process(self, pid: PID):
        if not pid:
            return
        try:
            os.kill(pid, signal.SIGTERM)
            time.sleep(0.2)
            os.kill(pid, signal.SIGKILL)  # force-kill if SIGTERM was ignored
        except ProcessLookupError:
            pass
        except Exception:
            pass

    def resize_window(self, handle: XWindow, width: int, height: int):
        _run(["xdotool", "windowsize", str(int(handle)), str(width), str(height)])

    def move_and_resize_window(self, handle: XWindow, left: int, top: int, width: int, height: int):
        _run(["xdotool", "windowmove", "--sync", str(int(handle)), str(left), str(top)])
        _run(["xdotool", "windowsize", "--sync", str(int(handle)), str(width), str(height)])

    def focus_window(self, handle: XWindow):
        self._try_focus_window(handle)

    def _try_focus_window(self, xid: XWindow) -> None:
        """Best-effort focus; on a bare Xvfb there is no WM, so this is a no-op."""
        if _run(["xdotool", "windowfocus", "--sync", str(int(xid))]) is None:
            _run(["xdotool", "windowactivate", "--sync", str(int(xid))])


class LinuxScreenCapturer(IScreenCapturer):
    def capture_window(self, handle: XWindow):
        # Xlib get_image reads the window's pixels directly; on a per-instance
        # Xvfb (software render, no compositor) this is exact and focus-free.
        try:
            from Xlib import X, display as _display

            disp = _display.Display()
            try:
                window = disp.create_resource_object("window", int(handle))
                geometry = window.get_geometry()
                width, height = geometry.width, geometry.height
                raw = window.get_image(0, 0, width, height, X.ZPixmap, 0xFFFFFFFF)
                buffer = raw.data
                if isinstance(buffer, str):  # older python-xlib returns str
                    buffer = buffer.encode("latin-1")
                arr = np.frombuffer(buffer, dtype=np.uint8).reshape((height, width, 4))
                return cv2.cvtColor(arr, cv2.COLOR_BGRA2BGR)
            finally:
                disp.close()
        except Exception as exc:
            raise RuntimeError(f"Failed to capture window {handle}: {exc}") from exc


class LinuxInputController(IInputController):
    def __init__(self, window_manager: IWindowManager):
        self._window_manager = window_manager

    def click(self, handle: XWindow, x_normalized: NormalizedCoord, y_normalized: NormalizedCoord):
        # Deliver to the specific window without raising/focusing it (fleet-safe).
        if not handle:
            return
        try:
            from Xlib import display as _display

            disp = _display.Display()
            try:
                window = disp.create_resource_object("window", int(handle))
                geometry = window.get_geometry()
                width, height = geometry.width, geometry.height
            finally:
                disp.close()
        except Exception:
            return

        x = int(x_normalized * width)
        y = int(y_normalized * height)
        xid = str(int(handle))
        _run(["xdotool", "mousemove", "--window", xid, str(x), str(y)])
        time.sleep(0.01)
        _run(["xdotool", "click", "--window", xid, "1"])

    def press_key(self, handle: XWindow, key_name: str):
        if not handle:
            return
        keysym = self._keysym_from_key_name(key_name)
        _run(["xdotool", "key", "--clearmodifiers", "--window", str(int(handle)), keysym])

    def _keysym_from_key_name(self, keyName: str) -> Keysym:
        """Resolve a human-readable key name to an xdotool keysym."""
        name = (keyName or "").strip()
        if not name:
            raise ValueError("Invalid key name: (empty)")

        norm = name.lower()
        if norm in _KEY_NAME_TO_KEYSYM:
            return _KEY_NAME_TO_KEYSYM[norm]

        # Function keys F1..F24
        if len(norm) >= 2 and norm[0] == "f" and norm[1:].isdigit():
            n = int(norm[1:])
            if 1 <= n <= 24:
                return f"F{n}"

        # Single visible character: xdotool accepts the literal keysym.
        if len(name) == 1:
            return name

        raise ValueError(f"Invalid key name: {keyName}")
