from __future__ import annotations

from typing import Optional

from Src.Helper import (
    FindHwndByTitle,
    FindPidByHwnd,
    LaunchProcessByExecutable,
    ResizeWindow,
)


class TargetWindowService:
    """Owns target window selection and basic process/window operations."""

    def __init__(self) -> None:
        self._currentWindowHandle: Optional[int] = None

    @property
    def CurrentWindowHandle(self) -> Optional[int]:
        return self._currentWindowHandle

    def SetWindowHandle(self, windowHandle: Optional[int]) -> None:
        self._currentWindowHandle = windowHandle

    def FindWindow(self, title: str) -> Optional[int]:
        windowHandle = FindHwndByTitle(title)
        self._currentWindowHandle = windowHandle
        return windowHandle

    def GetPidByHwnd(self, windowHandle: int) -> Optional[int]:
        if not windowHandle:
            return None
        return FindPidByHwnd(windowHandle)

    def GetCurrentTargetPid(self) -> Optional[int]:
        if not self._currentWindowHandle:
            return None
        return FindPidByHwnd(self._currentWindowHandle)

    def HasTargetWindow(self) -> bool:
        return self._currentWindowHandle is not None

    def LaunchApplication(self, path: str) -> Optional[int]:
        if path:
            return LaunchProcessByExecutable(path)
        return None

    def ResizeTargetWindow(self, width: int, height: int) -> None:
        if self._currentWindowHandle:
            ResizeWindow(self._currentWindowHandle, width, height)
