import time
import threading
from uuid import UUID
from typing import Callable, List, Optional, Any

import numpy as np

from Src.Helper import CaptureWindowByHwnd, IsHotkeyActive
from Src.Models import EventItem, ConditionItem
from Src.Engine.ConditionEngine import ConditionEngine, ConditionEngineContext
from Src.Engine.ActivationEngine import ActivationEngine, ActivationEngineContext
from Src.Engine.ActionExecutorEngine import ActionExecutorEngine, ActionExecutionContext


class TriggerMonitorService:
    def __init__(
        self,
        getEventItems: Callable[[], List[EventItem]],
        getConditionItems: Callable[[], List[ConditionItem]],
        getWindowHandle: Optional[Callable[[], Optional[int]]] = None,
        pollIntervalMs: int = 50,
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

        self._onEventDetected = onEventDetected
        self._onEventDisabled = onEventDisabled
        self._onFlowStateChanged = onFlowStateChanged
        self._onFlowHotkeyChanged = onFlowHotkeyChanged
        self._onMatchScoreUpdated = onMatchScoreUpdated

        self._stopEvent = threading.Event()
        self._thread: Optional[threading.Thread] = None

        self._imageLock = threading.Lock()
        self._currentImage: Optional[np.ndarray[Any, Any]] = None

        self._flowEnabled = True
        self._flowHotkeyVkCodes: List[int] = []
        self._flowHotkeyIsCurrentlyHeld = False

        self._resetLock = threading.Lock()
        self._resetAllRequested = False
        self._resetEventUuids: set[UUID] = set()
        self._resetConditionUuids: set[UUID] = set()

        self._conditionEngine = ConditionEngine()
        self._activationEngine = ActivationEngine()
        self._actionExecutor = ActionExecutorEngine()

        self._conditionContext = ConditionEngineContext()
        self._activationContext = ActivationEngineContext()
        self._actionExecutionContext = ActionExecutionContext()

    def RequestResetEvent(self, eventUuid: UUID) -> None:
        with self._resetLock:
            self._resetEventUuids.add(eventUuid)

    def RequestResetCondition(self, conditionUuid: UUID) -> None:
        with self._resetLock:
            self._resetConditionUuids.add(conditionUuid)

    def RequestResetAllRuntimeState(self) -> None:
        with self._resetLock:
            self._resetAllRequested = True
            self._resetEventUuids.clear()
            self._resetConditionUuids.clear()

    def _ApplyPendingResets(self) -> None:
        with self._resetLock:
            resetAll = self._resetAllRequested
            resetEvents = set(self._resetEventUuids)
            resetConditions = set(self._resetConditionUuids)
            self._resetAllRequested = False
            self._resetEventUuids.clear()
            self._resetConditionUuids.clear()

        if resetAll:
            self._conditionContext.States.clear()
            self._activationContext.eventStates.clear()
            self._actionExecutionContext.eventStates.clear()
            return

        for eventUuid in resetEvents:
            self._activationContext.eventStates.pop(eventUuid, None)
            self._actionExecutionContext.eventStates.pop(eventUuid, None)

        for conditionUuid in resetConditions:
            self._conditionContext.States.pop(conditionUuid, None)

    def Start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stopEvent.clear()
        self._thread = threading.Thread(target=self._Run, name="TriggerMonitorService", daemon=True)
        self._thread.start()

    def Stop(self) -> None:
        self._stopEvent.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._thread = None

    def SetImage(self, image: Optional[np.ndarray[Any, Any]]) -> None:
        with self._imageLock:
            self._currentImage = image

    def SetFlowEnabled(self, isEnabled: bool) -> None:
        self._flowEnabled = isEnabled
        if self._onFlowStateChanged is not None:
            self._onFlowStateChanged(self._flowEnabled)

    def ToggleFlowEnabled(self) -> None:
        self.SetFlowEnabled(not self._flowEnabled)

    def SetFlowHotkey(self, virtualKeyCodes: List[int]) -> None:
        self._flowHotkeyVkCodes = list(virtualKeyCodes)
        if self._onFlowHotkeyChanged is not None:
            self._onFlowHotkeyChanged(list(self._flowHotkeyVkCodes))

    def GetFlowHotkey(self) -> List[int]:
        return list(self._flowHotkeyVkCodes)

    def _CopyImageForProcessing(self) -> Optional[np.ndarray[Any, Any]]:
        with self._imageLock:
            localImage = self._currentImage
            self._currentImage = None
            return localImage

    def _CheckFlowHotkeyPressed(self) -> None:
        if self._flowHotkeyVkCodes:
            isDownNow = IsHotkeyActive(self._flowHotkeyVkCodes)
            if self._flowHotkeyIsCurrentlyHeld and not isDownNow:
                self.ToggleFlowEnabled()
            self._flowHotkeyIsCurrentlyHeld = isDownNow
        else:
            self._flowHotkeyIsCurrentlyHeld = False

    def _Run(self) -> None:
        while not self._stopEvent.is_set():
            self._CheckFlowHotkeyPressed()

            # Apply requested resets even while flow is disabled.
            self._ApplyPendingResets()

            if not self._flowEnabled:
                time.sleep(self._pollIntervalMs / 1000.0)
                continue

            localImage = self._CopyImageForProcessing()
            conditionItemsSnapshot = list(self._getConditionItems())
            eventItemsSnapshot = list(self._getEventItems())

            

            conditionEngineResult, self._conditionContext = self._conditionEngine.Loop(
                conditionItemsSnapshot,
                localImage,
                self._conditionContext
            )

            activationResult, self._activationContext = self._activationEngine.Loop(
                eventItemsSnapshot,
                conditionEngineResult,
                self._activationContext
            )

            if self._getWindowHandle is not None:
                hwnd = self._getWindowHandle()
                if hwnd is not None:
                    self._actionExecutionContext = self._actionExecutor.Loop(
                        hwnd,
                        eventItemsSnapshot,
                        activationResult.triggeredEventUuids,
                        self._actionExecutionContext,
                    )


            if self._onEventDetected is not None:
                for event in activationResult.triggered:
                    self._onEventDetected(event)

            if self._onEventDisabled is not None:
                for event in activationResult.disabled:
                    self._onEventDisabled(event)

            if self._onMatchScoreUpdated is not None:
                for update in conditionEngineResult.matchUpdates:
                    self._onMatchScoreUpdated(update)

            time.sleep(self._pollIntervalMs / 1000.0)


class LiveCaptureService:
    def __init__(
        self,
        windowHandle: int,
        intervalMs: int = 200,
        onImage: Optional[Callable[[Optional[np.ndarray[Any, Any]]], None]] = None,
    ) -> None:
        self._windowHandle = windowHandle
        self._intervalMs = intervalMs
        self._onImage = onImage

        self._stopEvent = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def Start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stopEvent.clear()
        self._thread = threading.Thread(target=self._Run, name="LiveCaptureService", daemon=True)
        self._thread.start()

    def Stop(self) -> None:
        self._stopEvent.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._thread = None

    def _Run(self) -> None:
        while not self._stopEvent.is_set():
            try:
                image = CaptureWindowByHwnd(self._windowHandle)
            except Exception as e:
                print(f"Live capture error: {e}")
                image = None
                self._stopEvent.set()

            if self._onImage is not None:
                self._onImage(image)

            time.sleep(self._intervalMs / 1000.0)