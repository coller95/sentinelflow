from __future__ import annotations

from typing import Optional

from Src.Helper import (
    KeyNameFromVk,
    VkFromKeyName,
    SendKeystrokeToWindow,
    SendMouseClickToWindow,
)


class InputAutomationService:
    def KeyNameFromVk(self, virtualKeyCode: int) -> str:
        return KeyNameFromVk(virtualKeyCode)

    def TrySendMouseClick(self, hwnd: Optional[int], normalizedX: float, normalizedY: float) -> bool:
        if not hwnd:
            return False
        SendMouseClickToWindow(hwnd, normalizedX, normalizedY)
        return True

    def TrySendKeystrokeByName(self, hwnd: Optional[int], keyName: str) -> bool:
        if not hwnd:
            return False
        virtualKeyCode = VkFromKeyName(keyName)
        if not virtualKeyCode:
            return False
        SendKeystrokeToWindow(hwnd, virtualKeyCode)
        return True
