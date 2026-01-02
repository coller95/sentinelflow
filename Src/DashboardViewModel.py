from typing import (
    List, Optional, Any
)
# Third-party imports
import numpy as np
from PySide6.QtCore import Signal, QObject

from Src.Models import (
    ActivationType,
    EventItem, RectangleRegion
)

from Src.Services.SentinelControllerService import SentinelControllerService
from Src.Services.TargetWindowService import TargetWindowService
from Src.Services.InputAutomationService import InputAutomationService
from Src.Services.StatePersistenceService import StatePersistenceService
from Src.Services.EventEditingService import EventEditingService
from Src.Services.EventListService import EventListService
from Src.Services.DashboardViewStateService import DashboardViewStateService


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

    def __init__(self) -> None:
        super().__init__()
        self.EventItems: List[EventItem] = []
        self.TargetWindowService = TargetWindowService()
        self.InputAutomationService = InputAutomationService()
        self.StatePersistenceService = StatePersistenceService()
        self.EventEditingService = EventEditingService()
        self.EventListService = EventListService()
        self.ViewState = DashboardViewStateService()
        self.LastLiveImage: Optional[np.ndarray[Any, Any]] = None
        self.SentinelController = SentinelControllerService(
            get_event_items=lambda: self.EventItems,
            get_window_handle=lambda: self.TargetWindowService.CurrentWindowHandle,
            poll_interval_ms=50,
            capture_interval_ms=200,
            on_image=self._onCaptureImage,
            on_event_detected=self._onEventDetected,
            on_event_disabled=self.EventItemChangedSignal.emit,
            on_flow_state_changed=self.EventExecutionStateChangedSignal.emit,
            on_flow_hotkey_changed=self.EventExecutionStateHotkeyChangedSignal.emit,
            on_match_score_updated=self.MatchScoreUpdated.emit,
        )
        self.StartSentinel()

    def AddEvent(self) -> None:
        newEvent = self.EventListService.CreateDefaultEvent()
        self.EventItems.append(newEvent)
        self.EventItemAddedSignal.emit(newEvent)

    def RemoveEvent(self) -> None:
        index = self.EventListService.RemoveSelectedEvent(self.EventItems, self.ViewState.SelectedEventItem)
        if index is not None:
            self.EventItemRemovedSignal.emit(index)

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
            self.StatePersistenceService.SaveState(filePath, events=self.EventItems, flow_hotkey=flowHotkey)
                
            print(f"State successfully saved to {filePath}")
        except Exception as e:
            print(f"SaveState Error: {e}")
            raise e

    def LoadState(self, filePath: str) -> None:
        try:
            loaded = self.StatePersistenceService.LoadState(filePath)
            if loaded is None:
                return

            loadedEvents, loadedHotkey, loadedVersion = loaded
            print(f"Loading new format (v{loadedVersion})")
                
            # ---------------------------
            # Populate the UI/Model
            self.SentinelController.SetFlowEnabled(False)  # Ensure flow is off during loading
                
            self.EventItems.clear()
            for event in loadedEvents:
                # Best-effort: ensure fresh transient state after load
                try:
                    event.ResetTransientState()
                except Exception:
                    pass
                self.EventItems.append(event)
                self.EventItemAddedSignal.emit(event)

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
