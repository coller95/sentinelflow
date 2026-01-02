from __future__ import annotations

from typing import Optional

from Src.Helper import (
    KeyNameFromVk,
    VkFromKeyName,
    SendKeystrokeToWindow,
    SendMouseClickToWindow,
)


class InputAutomationService:
    def KeyNameFromVk(self, virtual_key_code: int) -> str:
        return KeyNameFromVk(virtual_key_code)

    def TrySendMouseClick(self, hwnd: Optional[int], normalized_x: float, normalized_y: float) -> bool:
        if not hwnd:
            return False
        SendMouseClickToWindow(hwnd, normalized_x, normalized_y)
        return True

    def TrySendKeystrokeByName(self, hwnd: Optional[int], key_name: str) -> bool:
        if not hwnd:
            return False
        virtual_key_code = VkFromKeyName(key_name)
        if not virtual_key_code:
            return False
        SendKeystrokeToWindow(hwnd, virtual_key_code)
        return True
