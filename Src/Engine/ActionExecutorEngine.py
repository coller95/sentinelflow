import time
from typing import Any, List, Optional, cast

from Src.Helper import SendKeyChordToWindow, SendKeystrokeToWindow, SendMouseClickToWindow
from Src.Models import ActionItem, EventItem, InputType, MacroStep

class ActionExecutorEngine:
    def ExecuteEvent(self, windowHandle: int, event: EventItem) -> None:
        if not event.IsEnabled:
            return
        self.ExecuteAction(windowHandle, event.AssignedAction)

    def ExecuteAction(self, windowHandle: int, action: Optional[ActionItem]) -> None:
        if not action:
            return
        for step in action.MacroSteps:
            self.ExecuteStep(windowHandle, step)

    def ExecuteStep(self, windowHandle: int, step: MacroStep) -> None:
        if step.InputType == InputType.Keyboard:
            self._SendKeystroke(windowHandle, step.Value)
        elif step.InputType == InputType.Mouse:
            value = step.Value
            SendMouseClickToWindow(windowHandle, float(value[0]), float(value[1]))
        elif step.InputType == InputType.Delay:
            time.sleep(float(step.Value) / 1000.0)

    def _SendKeystroke(self, hwnd: int, value: Any) -> None:
        if isinstance(value, (list, tuple)):
            seq = cast(list[int] | tuple[int, ...], value)
            keys = [int(vk) for vk in seq]
            SendKeyChordToWindow(hwnd, keys)
            return
        SendKeystrokeToWindow(hwnd, int(value))

    def Loop(self, windowHandle: int, events: List[EventItem]) -> None:
        for event in events:
            self.ExecuteEvent(windowHandle, event)