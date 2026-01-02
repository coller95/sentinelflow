from __future__ import annotations

from typing import Any

from Src.Helper import KeyNameFromVk
from Src.Models import ActivationType, ConditionItem, EventItem, InputType, MacroStep, RectangleRegion


class EventEditingService:
    def SetEventEnabled(self, eventItem: EventItem, isEnabled: bool) -> None:
        eventItem.IsEnabled = isEnabled

    def UpdateEventName(self, eventItem: EventItem, name: str) -> None:
        eventItem.Name = name

    def UpdateActivationType(self, eventItem: EventItem, activationType: ActivationType) -> None:
        eventItem.SelectedActivationType = activationType

    def UpdateLoopCount(self, eventItem: EventItem, loopCount: int) -> None:
        eventItem.LoopCount = loopCount

    def UpdateLoopIntervalMs(self, eventItem: EventItem, intervalMs: int) -> None:
        eventItem.IntervalMilliseconds = intervalMs

    def UpdateThreshold(self, eventItem: EventItem, threshold: float) -> None:
        eventItem.Threshold = threshold

    def UpdateTriggerOnThresholdExceed(self, eventItem: EventItem, isEnabled: bool) -> None:
        eventItem.TriggerOnThresholdExceed = isEnabled

    def UpdateRetriggerTimeMs(self, eventItem: EventItem, retriggerTimeMs: float) -> None:
        eventItem.RetriggerTimeMilliseconds = retriggerTimeMs

    def UpdateActivationHotkey(self, eventItem: EventItem, virtualKeyCodes: list[int]) -> None:
        eventItem.ActivationVirtualKeyCodes = virtualKeyCodes

    def SetTemplateAndRoi(self, eventItem: EventItem, templateImage: Any, roi: RectangleRegion) -> None:
        eventItem.Condition.TemplateImage = templateImage
        eventItem.Condition.Roi = roi

    def SetCondition(self, eventItem: EventItem, condition: ConditionItem) -> None:
        eventItem.Condition = condition

    def AddMouseStep(self, eventItem: EventItem, normalizedX: float, normalizedY: float) -> None:
        if not eventItem.AssignedAction:
            return
        newStep = MacroStep(
            InputType.Mouse,
            (normalizedX, normalizedY),
            f"Click at ({normalizedX:.7f}, {normalizedY:.7f})",
        )
        eventItem.AssignedAction.AddStep(newStep)

    def AddKeyboardStep(self, eventItem: EventItem, virtualKeyCodes: list[int]) -> None:
        if not eventItem.AssignedAction:
            return
        keys = [int(vk) for vk in virtualKeyCodes]
        names = [KeyNameFromVk(vk) for vk in keys]
        description = f"Press \"{' + '.join(names)}\""
        newStep = MacroStep(InputType.Keyboard, keys, description)
        eventItem.AssignedAction.AddStep(newStep)

    def AddKeyboardHoldStep(self, eventItem: EventItem, virtualKeyCode: int) -> None:
        if not eventItem.AssignedAction:
            return
        vk = int(virtualKeyCode)
        name = KeyNameFromVk(vk)
        newStep = MacroStep(InputType.KeyboardHold, vk, f"Hold \"{name}\"")
        eventItem.AssignedAction.AddStep(newStep)

    def AddKeyboardReleaseStep(self, eventItem: EventItem, virtualKeyCode: int) -> None:
        if not eventItem.AssignedAction:
            return
        vk = int(virtualKeyCode)
        name = KeyNameFromVk(vk)
        newStep = MacroStep(InputType.KeyboardRelease, vk, f"Release \"{name}\"")
        eventItem.AssignedAction.AddStep(newStep)

    def AddDelayStep(self, eventItem: EventItem, milliseconds: int) -> None:
        if not eventItem.AssignedAction:
            return
        newStep = MacroStep(InputType.Delay, milliseconds, f"Wait {milliseconds}ms")
        eventItem.AssignedAction.AddStep(newStep)

    def RemoveStep(self, eventItem: EventItem, index: int) -> None:
        if not eventItem.AssignedAction:
            return
        eventItem.AssignedAction.RemoveStep(index)

    def MoveStep(self, eventItem: EventItem, fromIndex: int, toIndex: int) -> None:
        if not eventItem.AssignedAction:
            return
        steps = eventItem.AssignedAction.MacroSteps
        if fromIndex < 0 or fromIndex >= len(steps) or toIndex < 0 or toIndex >= len(steps):
            return
        steps[fromIndex], steps[toIndex] = steps[toIndex], steps[fromIndex]