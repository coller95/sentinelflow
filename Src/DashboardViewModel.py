from typing import (
    List, Optional, Any
)
from uuid import UUID
# Third-party imports
import numpy as np
from PySide6.QtCore import Signal, QObject

from Src.Models import (
    ActivationType,
    ConditionItem,
    ConditionType,
    CriteriaLogic,
    ConditionCriterion,
    EventItem, RectangleRegion
)

from Src.Services.SentinelControllerService import SentinelControllerService
from Src.Services.TargetWindowService import TargetWindowService
from Src.Services.InputAutomationService import InputAutomationService
from Src.Services.StatePersistenceService import StatePersistenceService
from Src.Services.EventEditingService import EventEditingService
from Src.Services.EventListService import EventListService
from Src.Services.DashboardViewStateService import DashboardViewStateService
from Src.Services.EventStoreService import EventStoreService
from Src.Services.ConditionStoreService import ConditionStoreService


class DashboardViewModel(QObject):
    EventItemAddedSignal = Signal(EventItem)
    EventItemRemovedSignal = Signal(int)
    EventItemSelectedSignal = Signal(EventItem)
    EventExecutionStateChangedSignal = Signal(bool)
    EventExecutionStateHotkeyChangedSignal = Signal(list)
    EventItemChangedSignal = Signal(EventItem)
    WindowHandleUpdated = Signal(object)
    CaptureImageReady = Signal(object)
    MatchScoreUpdated = Signal(object)
    ConditionsChangedSignal = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.EventStoreService = EventStoreService()
        self.ConditionStoreService = ConditionStoreService()
        self.TargetWindowService = TargetWindowService()
        self.InputAutomationService = InputAutomationService()
        self.StatePersistenceService = StatePersistenceService()
        self.EventEditingService = EventEditingService()
        self.EventListService = EventListService()
        self.ViewState = DashboardViewStateService()
        self.LastLiveImage: Optional[np.ndarray[Any, Any]] = None
        self.SentinelController = SentinelControllerService(
            getEventItems=self.EventStoreService.GetSnapshot,
            getConditionItems=self.ConditionStoreService.GetSnapshot,
            getWindowHandle=lambda: self.TargetWindowService.CurrentWindowHandle,
            pollIntervalMs=50,
            captureIntervalMs=200,
            onImage=self._onCaptureImage,
            onEventDetected=self._onEventDetected,
            onEventDisabled=self.EventItemChangedSignal.emit,
            onFlowStateChanged=self.EventExecutionStateChangedSignal.emit,
            onFlowHotkeyChanged=self.EventExecutionStateHotkeyChangedSignal.emit,
            onMatchScoreUpdated=self.MatchScoreUpdated.emit,
        )
        self.StartSentinel()

    def AddEvent(self) -> None:
        library = self.ConditionStoreService.GetSnapshot()
        if len(library) == 0:
            raise ValueError("Create a condition first")

        newEvent = self.EventListService.CreateDefaultEvent(condition=library[0])
        self.EventStoreService.Add(newEvent)
        self.ConditionsChangedSignal.emit()
        self.EventItemAddedSignal.emit(newEvent)

    def RemoveEvent(self) -> None:
        index = self.EventStoreService.RemoveSelected(self.ViewState.SelectedEventItem)
        if index is not None:
            self.EventItemRemovedSignal.emit(index)

    def MoveEvent(self, fromIndex: int, toIndex: int) -> None:
        self.EventStoreService.MoveByIndex(fromIndex, toIndex)

    def FindWindow(self, title: str) -> Optional[int]:
        windowHandle = self.TargetWindowService.FindWindow(title)
        self.WindowHandleUpdated.emit(windowHandle)
        return windowHandle

    def GetPidByHwnd(self, windowHandle: int) -> Optional[int]:
        return self.TargetWindowService.GetPidByHwnd(windowHandle)

    def GetCurrentTargetPid(self) -> Optional[int]:
        return self.TargetWindowService.GetCurrentTargetPid()

    def HasTargetWindow(self) -> bool:
        return self.TargetWindowService.HasTargetWindow()

    def KeyNameFromVk(self, virtualKeyCode: int) -> str:
        return self.InputAutomationService.KeyNameFromVk(virtualKeyCode)

    def LaunchApplication(self, path: str) -> Optional[int]:
        return self.TargetWindowService.LaunchApplication(path)

    def ResizeTargetWindow(self, width: int, height: int) -> None:
        self.TargetWindowService.ResizeTargetWindow(width, height)

    def ToggleCapture(self, active: bool) -> None:
        hwnd = self.TargetWindowService.CurrentWindowHandle
        self.SentinelController.ToggleCapture(active, hwnd)

    def GetLastLiveImage(self) -> Optional[np.ndarray[Any, Any]]:
        return self.LastLiveImage

    def _onCaptureImage(self, image: Optional[np.ndarray[Any, Any]]) -> None:
        self.LastLiveImage = image
        self.CaptureImageReady.emit(image)

    def StopCapture(self) -> None:
        self.SentinelController.StopCapture()

    def StartSentinel(self) -> None:
        self.SentinelController.StartSentinel()

    def StopSentinel(self) -> None:
        self.SentinelController.StopSentinel()

    def _onEventDetected(self, event: EventItem) -> None:
        print(f"Event Detected: {event.Name}")

    def SaveState(self, filePath: str) -> None:
        try:
            flowHotkey = self.SentinelController.GetFlowHotkey()
            self.StatePersistenceService.SaveState(
                filePath,
                events=self.EventStoreService.GetAll(),
                conditions=self.ConditionStoreService.GetSnapshot(),
                flowHotkey=flowHotkey,
            )
                
            print(f"State successfully saved to {filePath}")
        except Exception as e:
            print(f"SaveState Error: {e}")
            raise e

    def LoadState(self, filePath: str) -> None:
        try:
            loadedEvents, loadedHotkey, loadedVersion, loadedConditions = self.StatePersistenceService.LoadState(filePath)
            print(f"Loading new format (v{loadedVersion})")
                
            # ---------------------------
            # Populate the UI/Model
            self.SentinelController.SetFlowEnabled(False)  # Ensure flow is off during loading
            self.SentinelController.RequestResetAllRuntimeState()

            self.EventStoreService.Clear()

            # Restore condition library first (if present)
            self.ConditionStoreService.ReplaceAll(loadedConditions)

            self.ConditionsChangedSignal.emit()

            # Build a UUID->ConditionItem map for relinking (works even if loadedConditions is empty)
            conditionMap = {c.Uuid: c for c in self.ConditionStoreService.GetSnapshot()}
            for event in loadedEvents:
                # Ensure events reference the shared ConditionItem instance by UUID
                cid = event.Condition.Uuid
                shared = conditionMap.get(cid)
                if shared is None:
                    # Keep file self-consistent even if an event references an unlisted condition.
                    shared = event.Condition
                    conditionMap[cid] = shared
                    self.ConditionStoreService.Add(shared)
                event.Condition = shared

                self.EventStoreService.Add(event)
                self.EventItemAddedSignal.emit(event)

            self.ConditionsChangedSignal.emit()

            # Apply settings (also allow clearing hotkey by saving empty list)
            self.SentinelController.SetFlowHotkey(loadedHotkey)
        except Exception as e:
            print(f"LoadState Error: {e}")
            raise e

    def ToggleSentinelFlow(self) -> None:
        self.SentinelController.ToggleFlowEnabled()

    def SetSentinelFlowHotkey(self, virtualKeyCodes: List[int]) -> None:
        self.SentinelController.SetFlowHotkey(virtualKeyCodes)

    def SetEventEnabled(self, eventItem: EventItem, isEnabled: bool) -> None:
        self.EventEditingService.SetEventEnabled(eventItem, isEnabled)
        self.SentinelController.RequestResetEvent(eventItem.Uuid)
        self.EventItemChangedSignal.emit(eventItem)

    def UpdateSelectedEventName(self, name: str) -> None:
        eventItem = self.ViewState.SelectedEventItem
        if not eventItem:
            return
        self.EventEditingService.UpdateEventName(eventItem, name)
        self.EventItemChangedSignal.emit(eventItem)

    def UpdateSelectedActivationType(self, activationType: ActivationType) -> None:
        eventItem = self.ViewState.SelectedEventItem
        if not eventItem:
            return
        self.EventEditingService.UpdateActivationType(eventItem, activationType)

        if activationType == ActivationType.CriteriaMet and len(eventItem.Criteria) == 0:
            # Seed a first criterion using the current event condition (no new condition created).
            eventItem.Criteria.append(ConditionCriterion(eventItem.Condition.Uuid, threshold=eventItem.Threshold, triggerOnThresholdExceed=eventItem.TriggerOnThresholdExceed))
        self.SentinelController.RequestResetEvent(eventItem.Uuid)
        self.SentinelController.RequestResetCondition(eventItem.Condition.Uuid)
        self.EventItemChangedSignal.emit(eventItem)

    def UpdateSelectedLoopCount(self, loopCount: int) -> None:
        eventItem = self.ViewState.SelectedEventItem
        if not eventItem:
            return
        self.EventEditingService.UpdateLoopCount(eventItem, loopCount)
        self.EventItemChangedSignal.emit(eventItem)

    def UpdateSelectedLoopIntervalMs(self, intervalMs: int) -> None:
        eventItem = self.ViewState.SelectedEventItem
        if not eventItem:
            return
        self.EventEditingService.UpdateLoopIntervalMs(eventItem, intervalMs)
        self.EventItemChangedSignal.emit(eventItem)

    def UpdateSelectedThreshold(self, threshold: float) -> None:
        eventItem = self.ViewState.SelectedEventItem
        if not eventItem:
            return
        self.EventEditingService.UpdateThreshold(eventItem, threshold)
        self.EventItemChangedSignal.emit(eventItem)

    def UpdateSelectedTriggerOnThresholdExceed(self, isEnabled: bool) -> None:
        eventItem = self.ViewState.SelectedEventItem
        if not eventItem:
            return
        self.EventEditingService.UpdateTriggerOnThresholdExceed(eventItem, isEnabled)
        self.EventItemChangedSignal.emit(eventItem)

    def UpdateSelectedRetriggerTimeMs(self, retriggerTimeMs: float) -> None:
        eventItem = self.ViewState.SelectedEventItem
        if not eventItem:
            return
        self.EventEditingService.UpdateRetriggerTimeMs(eventItem, retriggerTimeMs)
        self.EventItemChangedSignal.emit(eventItem)

    def UpdateSelectedActivationHotkey(self, virtualKeyCodes: List[int]) -> None:
        eventItem = self.ViewState.SelectedEventItem
        if not eventItem:
            return
        self.EventEditingService.UpdateActivationHotkey(eventItem, virtualKeyCodes)
        self.EventItemChangedSignal.emit(eventItem)

    def SetSelectedTemplateAndRoi(self, templateImage: np.ndarray[Any, Any], roi: RectangleRegion) -> None:
        eventItem = self.ViewState.SelectedEventItem
        if not eventItem:
            return
        self.EventEditingService.SetTemplateAndRoi(eventItem, templateImage, roi)
        self.SentinelController.RequestResetCondition(eventItem.Condition.Uuid)
        self.EventItemChangedSignal.emit(eventItem)

    def GetConditionLibrary(self) -> list[ConditionItem]:
        return self.ConditionStoreService.GetSnapshot()

    def CreateCondition(self, name: str) -> ConditionItem:
        condition = ConditionItem()
        condition.Name = name
        self.ConditionStoreService.Add(condition)
        self.ConditionsChangedSignal.emit()
        return condition

    def DeleteCondition(self, conditionUuid: str) -> None:
        try:
            cid = UUID(conditionUuid)
        except Exception:
            return

        events = self.EventStoreService.GetAll()
        affectedEvents = [e for e in events if e.Condition.Uuid == cid]

        # Choose a fallback condition from the library, or create one if we're deleting the last.
        fallback = next((c for c in self.ConditionStoreService.GetSnapshot() if c.Uuid != cid), None)
        if fallback is None:
            fallback = ConditionItem()
            fallback.Name = "New Condition"
            self.ConditionStoreService.Add(fallback)

        for event in affectedEvents:
            self.EventEditingService.SetCondition(event, fallback)
            self.SentinelController.RequestResetEvent(event.Uuid)
            self.EventItemChangedSignal.emit(event)

        self.ConditionStoreService.RemoveByUuid(cid)
        self.SentinelController.RequestResetCondition(cid)
        self.SentinelController.RequestResetCondition(fallback.Uuid)
        self.ConditionsChangedSignal.emit()

    def RenameCondition(self, conditionUuid: str, name: str) -> None:
        try:
            cid = UUID(conditionUuid)
        except Exception:
            return

        condition = self.ConditionStoreService.GetByUuid(cid)
        if condition is None:
            return
        condition.Name = name
        self.ConditionsChangedSignal.emit()

    def MoveCondition(self, fromIndex: int, toIndex: int) -> None:
        self.ConditionStoreService.MoveByIndex(fromIndex, toIndex)
        self.ConditionsChangedSignal.emit()

    def SetConditionTemplateAndRoi(self, conditionUuid: str, templateImage: np.ndarray[Any, Any], roi: RectangleRegion) -> None:
        try:
            cid = UUID(conditionUuid)
        except Exception:
            return

        condition = self.ConditionStoreService.GetByUuid(cid)
        if condition is None:
            return

        condition.TemplateImage = templateImage
        condition.Roi = roi
        self.SentinelController.RequestResetCondition(condition.Uuid)
        self.ConditionsChangedSignal.emit()

    def SetConditionType(self, conditionUuid: str, conditionTypeName: str) -> None:
        try:
            cid = UUID(conditionUuid)
        except Exception:
            return

        condition = self.ConditionStoreService.GetByUuid(cid)
        if condition is None:
            return

        try:
            conditionType = ConditionType[conditionTypeName]
        except Exception:
            conditionType = ConditionType.NotSet

        condition.SelectedConditionType = conditionType
        self.SentinelController.RequestResetCondition(condition.Uuid)
        self.ConditionsChangedSignal.emit()

    def SetSelectedEventCondition(self, conditionUuid: str) -> None:
        eventItem = self.ViewState.SelectedEventItem
        if not eventItem:
            return
        try:
            cid = UUID(conditionUuid)
        except Exception:
            return

        condition = self.ConditionStoreService.GetByUuid(cid)
        if condition is None:
            return
        self.EventEditingService.SetCondition(eventItem, condition)
        self.SentinelController.RequestResetEvent(eventItem.Uuid)
        self.EventItemChangedSignal.emit(eventItem)

    def GetSelectedCriteria(self) -> list[ConditionCriterion]:
        eventItem = self.ViewState.SelectedEventItem
        if not eventItem:
            return []
        return list(eventItem.Criteria)

    def GetSelectedCriteriaLogic(self) -> CriteriaLogic:
        eventItem = self.ViewState.SelectedEventItem
        if not eventItem:
            return CriteriaLogic.All
        return eventItem.CriteriaLogic

    def SetSelectedCriteriaLogic(self, logicName: str) -> None:
        eventItem = self.ViewState.SelectedEventItem
        if not eventItem:
            return
        try:
            logic = CriteriaLogic[logicName]
        except Exception:
            logic = CriteriaLogic.All
        eventItem.CriteriaLogic = logic
        self.SentinelController.RequestResetEvent(eventItem.Uuid)
        self.EventItemChangedSignal.emit(eventItem)

    def AddSelectedCriterion(self) -> None:
        eventItem = self.ViewState.SelectedEventItem
        if not eventItem:
            return
        library = self.ConditionStoreService.GetSnapshot()
        if len(library) == 0:
            return
        eventItem.Criteria.append(ConditionCriterion(library[0].Uuid, threshold=0.99, triggerOnThresholdExceed=True))
        self.SentinelController.RequestResetEvent(eventItem.Uuid)
        self.EventItemChangedSignal.emit(eventItem)

    def RemoveSelectedCriterion(self, index: int) -> None:
        eventItem = self.ViewState.SelectedEventItem
        if not eventItem:
            return
        if index < 0 or index >= len(eventItem.Criteria):
            return
        eventItem.Criteria.pop(index)
        self.SentinelController.RequestResetEvent(eventItem.Uuid)
        self.EventItemChangedSignal.emit(eventItem)

    def UpdateSelectedCriterionCondition(self, index: int, conditionUuid: str) -> None:
        eventItem = self.ViewState.SelectedEventItem
        if not eventItem:
            return
        if index < 0 or index >= len(eventItem.Criteria):
            return
        try:
            cid = UUID(conditionUuid)
        except Exception:
            return
        eventItem.Criteria[index].ConditionUuid = cid
        self.SentinelController.RequestResetEvent(eventItem.Uuid)
        self.EventItemChangedSignal.emit(eventItem)

    def UpdateSelectedCriterionThreshold(self, index: int, threshold: float) -> None:
        eventItem = self.ViewState.SelectedEventItem
        if not eventItem:
            return
        if index < 0 or index >= len(eventItem.Criteria):
            return
        eventItem.Criteria[index].Threshold = threshold
        self.SentinelController.RequestResetEvent(eventItem.Uuid)
        self.EventItemChangedSignal.emit(eventItem)

    def UpdateSelectedCriterionTriggerOnThresholdExceed(self, index: int, isEnabled: bool) -> None:
        eventItem = self.ViewState.SelectedEventItem
        if not eventItem:
            return
        if index < 0 or index >= len(eventItem.Criteria):
            return
        eventItem.Criteria[index].TriggerOnThresholdExceed = isEnabled
        self.SentinelController.RequestResetEvent(eventItem.Uuid)
        self.EventItemChangedSignal.emit(eventItem)

    def AddSelectedMouseStepFromCapturedPosition(self) -> None:
        eventItem = self.ViewState.SelectedEventItem
        if not eventItem or not eventItem.AssignedAction:
            return
        if self.ViewState.CaptureMousePositionNormalized is None:
            raise ValueError("No mouse position captured")
        normalizedX, normalizedY = self.ViewState.CaptureMousePositionNormalized
        self.EventEditingService.AddMouseStep(eventItem, normalizedX, normalizedY)
        self.EventItemChangedSignal.emit(eventItem)

    def AddSelectedKeyboardStep(self, virtualKeyCodes: list[int]) -> None:
        eventItem = self.ViewState.SelectedEventItem
        if not eventItem or not eventItem.AssignedAction:
            return

        self.EventEditingService.AddKeyboardStep(eventItem, virtualKeyCodes)
        self.EventItemChangedSignal.emit(eventItem)

    def AddSelectedKeyboardHoldStep(self, virtualKeyCode: int) -> None:
        eventItem = self.ViewState.SelectedEventItem
        if not eventItem or not eventItem.AssignedAction:
            return
        self.EventEditingService.AddKeyboardHoldStep(eventItem, virtualKeyCode)
        self.EventItemChangedSignal.emit(eventItem)

    def AddSelectedKeyboardReleaseStep(self, virtualKeyCode: int) -> None:
        eventItem = self.ViewState.SelectedEventItem
        if not eventItem or not eventItem.AssignedAction:
            return
        self.EventEditingService.AddKeyboardReleaseStep(eventItem, virtualKeyCode)
        self.EventItemChangedSignal.emit(eventItem)

    def AddSelectedDelayStep(self, milliseconds: int) -> None:
        eventItem = self.ViewState.SelectedEventItem
        if not eventItem or not eventItem.AssignedAction:
            return
        self.EventEditingService.AddDelayStep(eventItem, milliseconds)
        self.EventItemChangedSignal.emit(eventItem)

    def RemoveSelectedStep(self, index: int) -> None:
        eventItem = self.ViewState.SelectedEventItem
        if not eventItem or not eventItem.AssignedAction:
            return
        self.EventEditingService.RemoveStep(eventItem, index)
        self.EventItemChangedSignal.emit(eventItem)

    def MoveSelectedStep(self, fromIndex: int, toIndex: int) -> None:
        eventItem = self.ViewState.SelectedEventItem
        if not eventItem or not eventItem.AssignedAction:
            return
        self.EventEditingService.MoveStep(eventItem, fromIndex, toIndex)
        self.EventItemChangedSignal.emit(eventItem)

    def TrySendMouseClick(self, normalizedX: float, normalizedY: float) -> bool:
        hwnd = self.TargetWindowService.CurrentWindowHandle
        return self.InputAutomationService.TrySendMouseClick(hwnd, normalizedX, normalizedY)

    def TrySendKeystrokeByName(self, keyName: str) -> bool:
        hwnd = self.TargetWindowService.CurrentWindowHandle
        return self.InputAutomationService.TrySendKeystrokeByName(hwnd, keyName)

    @property
    def SelectedEventItem(self) -> Optional[EventItem]:
        return self.ViewState.SelectedEventItem

    @SelectedEventItem.setter
    def SelectedEventItem(self, event: Optional[EventItem]) -> None:        
        self.ViewState.SelectedEventItem = event
        self.EventItemSelectedSignal.emit(event)

    @property
    def CaptureMousePositionNormalized(self) -> Optional[tuple[float, float]]:
        return self.ViewState.CaptureMousePositionNormalized
    
    @CaptureMousePositionNormalized.setter
    def CaptureMousePositionNormalized(self, point: Optional[tuple[float, float]]) -> None:
        self.ViewState.CaptureMousePositionNormalized = point
