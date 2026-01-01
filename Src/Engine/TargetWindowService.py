from __future__ import annotations

from typing import Optional

from Src.Helper import (
    FindHwndByTitle,
    FindPidByHwnd,
    LaunchHwndByExecutable,
    ResizeWindow,
)


class TargetWindowService:
    """Owns target window selection and basic process/window operations."""

    def __init__(self) -> None:
        self._current_window_handle: Optional[int] = None

    @property
    def CurrentWindowHandle(self) -> Optional[int]:
        return self._current_window_handle

    def SetWindowHandle(self, window_handle: Optional[int]) -> None:
        self._current_window_handle = window_handle

    def FindWindow(self, title: str) -> Optional[int]:
        window_handle = FindHwndByTitle(title)
        self._current_window_handle = window_handle
        return window_handle

    def GetPidByHwnd(self, window_handle: int) -> Optional[int]:
        if not window_handle:
            return None
        return FindPidByHwnd(window_handle)

    def GetCurrentTargetPid(self) -> Optional[int]:
        if not self._current_window_handle:
            return None
        return FindPidByHwnd(self._current_window_handle)

    def HasTargetWindow(self) -> bool:
        return self._current_window_handle is not None

    def LaunchApplication(self, path: str) -> Optional[int]:
        if path:
            return LaunchHwndByExecutable(path)
        return None

    def ResizeTargetWindow(self, width: int, height: int) -> None:
        if self._current_window_handle:
            ResizeWindow(self._current_window_handle, width, height)
