from Src.Helper import *

class Services:
    def __init__(self):
        self._pid = 0
        self._hwnd = 0

    def LaunchApp(self, app_path: str) -> None:
        self.LaucnhApp(app_path)

    def LaucnhApp(self, app_path: str) -> None:
        self._pid = LaunchProcessByExecutable(app_path)
        self._hwnd = FindHwndByPid(self._pid)
        if self._hwnd is None:
            raise Exception("Failed to find window handle for launched application.")
        ResizeAndRepositionWindow(self._hwnd, 0, 0, 640, 480)

    def AttachApp(self, window_title: str) -> None:
        self._hwnd = FindHwndByTitle(window_title)
        if self._hwnd is None:
            raise Exception("Failed to find window handle for the specified title.")
        self._pid = FindPidByHwnd(self._hwnd)

    def CloseApp(self) -> None:
        if self._pid != 0:
            TerminateProcessByPid(self._pid)
            self._pid = 0
            self._hwnd = 0

