import ctypes
import shlex
import subprocess
import time
from pathlib import Path
from typing import Any, List, Optional

import cv2
import numpy as np
import win32api
import win32con
import win32gui
import win32process
import win32ui

from Src.domain.interfaces import IWindowManager, IScreenCapturer, IInputController

# Type aliases for internal use
HWND = int
PID = int
VirtualKey = int
NormalizedCoord = float


class WindowsWindowManager(IWindowManager):
    def find_window_by_title(self, title: str) -> Optional[HWND]:
        hwnd: HWND = win32gui.FindWindow(None, title)
        return hwnd if hwnd != 0 else None

    def find_pid_by_window(self, handle: HWND) -> PID:
        _, pid = win32process.GetWindowThreadProcessId(handle)
        return pid

    def find_window_by_pid(self, pid: PID) -> Optional[HWND]:
        def EnumWindowsCallback(hwnd: HWND, pidToFind: PID) -> bool:
            _, windowPid = win32process.GetWindowThreadProcessId(hwnd)
            if windowPid == pidToFind:
                nonlocal foundHwnd
                foundHwnd = hwnd
                return False  # Stop enumeration
            return True  # Continue enumeration

        foundHwnd: Optional[HWND] = None
        win32gui.EnumWindows(EnumWindowsCallback, pid)
        return foundHwnd

    def launch_process(self, executable_path: str) -> PID:
        command = executable_path.strip()
        if not command:
            raise ValueError("Executable path cannot be empty.")

        try:
            argv = shlex.split(command, posix=False)
        except ValueError:
            argv = [command]

        recoveredArgv: Optional[List[str]] = None
        if argv:
            for i in range(1, len(argv) + 1):
                candidate = " ".join(argv[:i]).strip('"')
                candidatePath = Path(candidate)
                if candidatePath.exists() and candidatePath.suffix.lower() in (".exe", ".com"):
                    recoveredArgv = [candidate] + argv[i:]
                    break

        argvToUse = recoveredArgv or argv

        exeCandidate = argvToUse[0].strip('"') if argvToUse else command.strip('"')
        exePath = Path(exeCandidate)
        suffix = exePath.suffix.lower()

        useShell = True
        popenArg: Any = command

        if exePath.exists() and suffix in (".exe", ".com"):
            useShell = False
            popenArg = argvToUse
        elif exePath.exists() and suffix in (".bat", ".cmd"):
            useShell = True
            popenArg = command

        process = subprocess.Popen(popenArg, shell=useShell)
        time.sleep(1.5)  # Allow time for window creation
        return process.pid

    def terminate_process(self, pid: PID) -> None:
        PROCESS_TERMINATE = 1
        handle = win32api.OpenProcess(PROCESS_TERMINATE, False, pid)
        if handle:
            win32api.TerminateProcess(handle, -1)
            win32api.CloseHandle(handle)

    def resize_window(self, handle: HWND, width: int, height: int) -> None:
        left, top, _, _ = win32gui.GetWindowRect(handle)
        win32gui.MoveWindow(handle, left, top, width, height, True)

    def move_and_resize_window(self, handle: HWND, left: int, top: int, width: int, height: int) -> None:
        win32gui.MoveWindow(handle, left, top, width, height, True)

    def focus_window(self, handle: HWND) -> None:
        self._try_focus_window(handle)

    def _try_focus_window(self, hwnd: HWND) -> None:
        """Best-effort focus/activate a window."""
        try:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        except Exception:
            pass

        try:
            win32gui.BringWindowToTop(hwnd)
        except Exception:
            pass

        try:
            win32gui.SetForegroundWindow(hwnd)
            return
        except Exception:
            pass

        # Fallback: temporarily attach thread input
        try:
            currentThreadId = win32api.GetCurrentThreadId()  # type: ignore
            targetThreadId, _ = win32process.GetWindowThreadProcessId(hwnd)
            win32process.AttachThreadInput(currentThreadId, targetThreadId, True)  # type: ignore
            try:
                try:
                    win32gui.SetActiveWindow(hwnd)  # type: ignore
                except Exception:
                    pass
                try:
                    win32gui.SetForegroundWindow(hwnd)
                except Exception:
                    pass
            finally:
                win32process.AttachThreadInput(currentThreadId, targetThreadId, False)  # type: ignore
        except Exception:
            pass


class WindowsScreenCapturer(IScreenCapturer):
    def capture_window(self, handle: HWND) -> Any:
        left, top, right, bottom = win32gui.GetWindowRect(handle)
        width = right - left
        height = bottom - top

        windowDc = win32gui.GetWindowDC(handle)
        memoryDc = win32ui.CreateDCFromHandle(windowDc)
        compatibleDc = memoryDc.CreateCompatibleDC()
        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(memoryDc, width, height)
        compatibleDc.SelectObject(bitmap)

        user32 = ctypes.windll.user32
        pwRenderFullContent = 0x00000002  # Windows 8+

        result = 0
        try:
            result = user32.PrintWindow(handle, compatibleDc.GetSafeHdc(), pwRenderFullContent)
        except Exception:
            result = user32.PrintWindow(handle, compatibleDc.GetSafeHdc(), 0)

        bitmapBits = bitmap.GetBitmapBits(True)
        imageArray = np.frombuffer(bitmapBits, dtype=np.uint8).reshape((height, width, 4))
        bgrImage = cv2.cvtColor(imageArray, cv2.COLOR_BGRA2BGR)

        # Cleanup
        win32gui.DeleteObject(bitmap.GetHandle())
        compatibleDc.DeleteDC()
        memoryDc.DeleteDC()
        win32gui.ReleaseDC(handle, windowDc)

        if result != 1:
            raise RuntimeError("Failed to capture window using PrintWindow.")
        return bgrImage


class WindowsInputController(IInputController):
    def __init__(self, window_manager: IWindowManager):
        self._window_manager = window_manager

    def click(self, handle: HWND, x_normalized: float, y_normalized: float) -> None:
        if not handle:
            return

        left, top, right, bottom = win32gui.GetWindowRect(handle)
        windowWidth = right - left
        windowHeight = bottom - top

        screenX = left + int(x_normalized * windowWidth)
        screenY = top + int(y_normalized * windowHeight)

        self._window_manager.focus_window(handle)
        time.sleep(0.05)

        win32api.SetCursorPos((screenX, screenY))
        time.sleep(0.05)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, screenX, screenY, 0, 0)  # type: ignore
        time.sleep(0.01)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, screenX, screenY, 0, 0)  # type: ignore

    def press_key(self, handle: HWND, key_name: str) -> None:
        if not handle:
            return

        vk = self._vk_from_key_name(key_name)
        
        self._window_manager.focus_window(handle)
        time.sleep(0.05)

        win32api.keybd_event(vk, 0, 0, 0)  # type: ignore
        win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)  # type: ignore

    def _vk_from_key_name(self, keyName: str) -> VirtualKey:
        name = (keyName or "").strip()
        if not name:
            raise ValueError("Invalid key name: (empty)")

        # Common named keys.
        norm = name.lower()
        named: dict[str, int] = {
            "enter": win32con.VK_RETURN,
            "return": win32con.VK_RETURN,
            "tab": win32con.VK_TAB,
            "escape": win32con.VK_ESCAPE,
            "esc": win32con.VK_ESCAPE,
            "space": win32con.VK_SPACE,
            "spacebar": win32con.VK_SPACE,
            "backspace": win32con.VK_BACK,
            "delete": win32con.VK_DELETE,
            "del": win32con.VK_DELETE,
            "insert": win32con.VK_INSERT,
            "home": win32con.VK_HOME,
            "end": win32con.VK_END,
            "pageup": win32con.VK_PRIOR,
            "pagedown": win32con.VK_NEXT,
            "left": win32con.VK_LEFT,
            "right": win32con.VK_RIGHT,
            "up": win32con.VK_UP,
            "down": win32con.VK_DOWN,
            "arrowleft": win32con.VK_LEFT,
            "arrowright": win32con.VK_RIGHT,
            "arrowup": win32con.VK_UP,
            "arrowdown": win32con.VK_DOWN,
            "lctrl": 0xA2,
            "rctrl": 0xA3,
            "lshift": 0xA0,
            "rshift": 0xA1,
            "lalt": 0xA4,
            "ralt": 0xA5,
            "numlock": win32con.VK_NUMLOCK,
            "numpad0": win32con.VK_NUMPAD0,
            "numpad1": win32con.VK_NUMPAD1,
            "numpad2": win32con.VK_NUMPAD2,
            "numpad3": win32con.VK_NUMPAD3,
            "numpad4": win32con.VK_NUMPAD4,
            "numpad5": win32con.VK_NUMPAD5,
            "numpad6": win32con.VK_NUMPAD6,
            "numpad7": win32con.VK_NUMPAD7,
            "numpad8": win32con.VK_NUMPAD8,
            "numpad9": win32con.VK_NUMPAD9,
            "numpadadd": win32con.VK_ADD,
            "numpadsubtract": win32con.VK_SUBTRACT,
            "numpadmultiply": win32con.VK_MULTIPLY,
            "numpaddivide": win32con.VK_DIVIDE,
            "numpaddecimal": win32con.VK_DECIMAL,
            "numpadcomma": win32con.VK_DECIMAL,
            "numpadclear": win32con.VK_CLEAR,
            "numpadenter": win32con.VK_RETURN,
        }

        oem_equal = getattr(win32con, "VK_OEM_NEC_EQUAL", None)
        if isinstance(oem_equal, int):
            named["numpadequal"] = oem_equal

        if norm in named:
            return VirtualKey(named[norm])

        # Function keys: F1..F24
        if len(norm) >= 2 and norm[0] == "f" and norm[1:].isdigit():
            n = int(norm[1:])
            if 1 <= n <= 24:
                return VirtualKey(win32con.VK_F1 + (n - 1))

        # Single visible character.
        if len(name) == 1:
            vk = VirtualKey(win32api.VkKeyScan(name))  # type: ignore
            if vk == -1:
                raise ValueError(f"Invalid key name: {keyName}")
            return vk & 0xFF

        raise ValueError(f"Invalid key name: {keyName}")
