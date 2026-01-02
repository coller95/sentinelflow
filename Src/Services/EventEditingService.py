from __future__ import annotations

from typing import Any

from Src.Helper import KeyNameFromVk
from Src.Models import ActivationType, EventItem, InputType, MacroStep, RectangleRegion


class EventEditingService:
    def SetEventEnabled(self, event_item: EventItem, is_enabled: bool) -> None:
        event_item.IsEnabled = is_enabled
        event_item.ResetTransientState()

    def UpdateEventName(self, event_item: EventItem, name: str) -> None:
        event_item.Name = name

    def UpdateActivationType(self, event_item: EventItem, activation_type: ActivationType) -> None:
        event_item.SelectedActivationType = activation_type
        event_item.ResetTransientState()

    def UpdateLoopCount(self, event_item: EventItem, loop_count: int) -> None:
        event_item.LoopCount = loop_count

    def UpdateLoopIntervalMs(self, event_item: EventItem, interval_ms: int) -> None:
        event_item.IntervalMilliseconds = interval_ms

    def UpdateThreshold(self, event_item: EventItem, threshold: float) -> None:
        event_item.Threshold = threshold

    def UpdateTriggerOnThresholdExceed(self, event_item: EventItem, is_enabled: bool) -> None:
        event_item.TriggerOnThresholdExceed = is_enabled

    def UpdateRetriggerTimeMs(self, event_item: EventItem, retrigger_time_ms: float) -> None:
        event_item.RetriggerTimeMilliseconds = retrigger_time_ms

    def UpdateActivationHotkey(self, event_item: EventItem, virtual_key_codes: list[int]) -> None:
        event_item.ActivationVirtualKeyCodes = virtual_key_codes

    def SetTemplateAndRoi(self, event_item: EventItem, template_image: Any, roi: RectangleRegion) -> None:
        event_item.TemplateImage = template_image
        event_item.Roi = roi

    def AddMouseStep(self, event_item: EventItem, normalized_x: float, normalized_y: float) -> None:
        if not event_item.AssignedAction:
            return
        new_step = MacroStep(
            InputType.Mouse,
            (normalized_x, normalized_y),
            f"Click at ({normalized_x:.7f}, {normalized_y:.7f})",
        )
        event_item.AssignedAction.AddStep(new_step)

    def AddKeyboardStep(self, event_item: EventItem, virtual_key_codes: list[int]) -> None:
        if not event_item.AssignedAction:
            return
        
        keys = [int(vk) for vk in virtual_key_codes]
        names = [KeyNameFromVk(vk) for vk in keys]
        description = f"Press \"{' + '.join(names)}\""
        new_step = MacroStep(InputType.Keyboard, keys, description)

        event_item.AssignedAction.AddStep(new_step)

    def AddDelayStep(self, event_item: EventItem, milliseconds: int) -> None:
        if not event_item.AssignedAction:
            return
        new_step = MacroStep(InputType.Delay, milliseconds, f"Wait {milliseconds}ms")
        event_item.AssignedAction.AddStep(new_step)

    def RemoveStep(self, event_item: EventItem, index: int) -> None:
        if not event_item.AssignedAction:
            return
        event_item.AssignedAction.RemoveStep(index)

    def MoveStep(self, event_item: EventItem, from_index: int, to_index: int) -> None:
        if not event_item.AssignedAction:
            return
        steps = event_item.AssignedAction.MacroSteps
        if from_index < 0 or from_index >= len(steps) or to_index < 0 or to_index >= len(steps):
            return
        steps[from_index], steps[to_index] = steps[to_index], steps[from_index]