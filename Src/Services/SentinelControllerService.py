from __future__ import annotations

from typing import Callable, List, Optional, Any
from uuid import UUID

import numpy as np

from Src.Models import EventItem, ConditionItem
from Src.Services.SentinelServices import TriggerMonitorService, LiveCaptureService


class SentinelControllerService:
    def __init__(
        self,
        *,
        getEventItems: Callable[[], List[EventItem]],
        getConditionItems: Callable[[], List[ConditionItem]],
        getWindowHandle: Callable[[], Optional[int]],
        pollIntervalMs: int = 50,
        captureIntervalMs: int = 200,
        onImage: Optional[Callable[[Optional[np.ndarray[Any, Any]]], None]] = None,
        onEventDetected: Optional[Callable[[EventItem], None]] = None,
        onEventDisabled: Optional[Callable[[EventItem], None]] = None,
        onFlowStateChanged: Optional[Callable[[bool], None]] = None,
        onFlowHotkeyChanged: Optional[Callable[[List[int]], None]] = None,
        onMatchScoreUpdated: Optional[Callable[[object], None]] = None,
    ) -> None:
        self._getEventItems = getEventItems
        self._getConditionItems = getConditionItems
        self._getWindowHandle = getWindowHandle
        self._pollIntervalMs = pollIntervalMs
        self._captureIntervalMs = captureIntervalMs
        self._onImage = onImage
        self._triggerThread: Optional[TriggerMonitorService] = None
        self._liveThread: Optional[LiveCaptureService] = None
        self._onEventDetected = onEventDetected
        self._onEventDisabled = onEventDisabled
        self._onFlowStateChanged = onFlowStateChanged
        self._onFlowHotkeyChanged = onFlowHotkeyChanged
        self._onMatchScoreUpdated = onMatchScoreUpdated

    def StartSentinel(self) -> None:
        if self._triggerThread is not None:
            return
        self._triggerThread = TriggerMonitorService(
            getEventItems=self._getEventItems,
            getConditionItems=self._getConditionItems,
            getWindowHandle=self._getWindowHandle,
            pollIntervalMs=self._pollIntervalMs,
            onEventDetected=self._onEventDetected,
            onEventDisabled=self._onEventDisabled,
            onFlowStateChanged=self._onFlowStateChanged,
            onFlowHotkeyChanged=self._onFlowHotkeyChanged,
            onMatchScoreUpdated=self._onMatchScoreUpdated,
        )
        self._triggerThread.Start()

    def StopSentinel(self) -> None:
        if self._triggerThread is not None:
            self._triggerThread.Stop()
            self._triggerThread = None

    def ToggleFlowEnabled(self) -> None:
        if self._triggerThread is not None:
            self._triggerThread.ToggleFlowEnabled()

    def SetFlowEnabled(self, isEnabled: bool) -> None:
        if self._triggerThread is not None:
            self._triggerThread.SetFlowEnabled(isEnabled)

    def SetFlowHotkey(self, virtualKeyCodes: List[int]) -> None:
        if self._triggerThread is not None:
            self._triggerThread.SetFlowHotkey(virtualKeyCodes)

    def GetFlowHotkey(self) -> List[int]:
        if self._triggerThread is None:
            return []
        return self._triggerThread.GetFlowHotkey()

    def SetImage(self, image: Optional[np.ndarray[Any, Any]]) -> None:
        if self._triggerThread is not None:
            self._triggerThread.SetImage(image)

    # -------------------- Runtime state reset --------------------

    def RequestResetEvent(self, eventUuid: UUID) -> None:
        if self._triggerThread is not None:
            self._triggerThread.RequestResetEvent(eventUuid)

    def RequestResetCondition(self, conditionUuid: UUID) -> None:
        if self._triggerThread is not None:
            self._triggerThread.RequestResetCondition(conditionUuid)

    def RequestResetAllRuntimeState(self) -> None:
        if self._triggerThread is not None:
            self._triggerThread.RequestResetAllRuntimeState()

    # -------------------- Capture --------------------

    def ToggleCapture(self, active: bool, windowHandle: Optional[int]) -> None:
        if active and windowHandle:
            self.StopCapture()
            self._liveThread = LiveCaptureService(
                windowHandle=windowHandle,
                intervalMs=self._captureIntervalMs,
                onImage=self._HandleImageCaptured,
            )
            self._liveThread.Start()
        else:
            self.StopCapture()

    def StopCapture(self) -> None:
        if self._liveThread is not None:
            self._liveThread.Stop()
            self._liveThread = None

    def _HandleImageCaptured(self, image: Optional[np.ndarray[Any, Any]]) -> None:
        # Preserve the old wiring: captured image flows to UI and to trigger engine.
        if self._onImage is not None:
            self._onImage(image)
        self.SetImage(image)
