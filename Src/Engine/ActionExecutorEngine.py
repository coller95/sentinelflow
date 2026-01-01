import time
from typing import Any, List, Optional, cast

from Src.Helper import SendKeyChordToWindow, SendKeystrokeToWindow, SendMouseClickToWindow
from Src.Models import ActionItem, EventItem, InputType, MacroStep

class ActionExecutorEngine:
    """Executes actions described by the model (side effects live here, not in Models)."""

    def execute_event(self, windowHandle: int, event: EventItem) -> None:
        if not event.IsEnabled:
            return
        self.execute_action(windowHandle, event.AssignedAction)

    def execute_action(self, windowHandle: int, action: Optional[ActionItem]) -> None:
        if not action:
            return
        for step in action.MacroSteps:
            self.execute_step(windowHandle, step)

    def execute_step(self, windowHandle: int, step: MacroStep) -> None:
        if step.InputType == InputType.Keyboard:
            self._send_keystroke(windowHandle, step.Value)
        elif step.InputType == InputType.Mouse:
            value = step.Value
            SendMouseClickToWindow(windowHandle, float(value[0]), float(value[1]))
        elif step.InputType == InputType.Delay:
            time.sleep(float(step.Value) / 1000.0)

    def _send_keystroke(self, hwnd: int, value: Any) -> None:
        if isinstance(value, (list, tuple)):
            seq = cast(list[int] | tuple[int, ...], value)
            keys = [int(vk) for vk in seq]
            SendKeyChordToWindow(hwnd, keys)
            return
        SendKeystrokeToWindow(hwnd, int(value))

    def loop(self, windowHandle: int, events: List[EventItem]) -> None:
        for event in events:
            self.execute_event(windowHandle, event)