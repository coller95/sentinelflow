from typing import (
    List, Optional, Any
)
# Third-party imports
import numpy as np
from PySide6.QtCore import Signal, QObject

from Src.Models import (
    ActivationType,
    ActionItem, EventItem, RectangleRegion
)

from Src.Engine.SentinelControllerService import SentinelControllerService
from Src.Engine.TargetWindowService import TargetWindowService
from Src.Engine.InputAutomationService import InputAutomationService
from Src.Engine.StatePersistenceService import StatePersistenceService
from Src.Engine.EventEditingService import EventEditingService

class DashboardViewModel(QObject):
    EventItemAddedSignal = Signal(EventItem)
    EventItemRemovedSignal = Signal(int)
    EventItemSelectedSignal = Signal(EventItem)
    EventExecutionStateChangedSignal = Signal(bool)  # Flow state
    EventExecutionStateHotkeyChangedSignal = Signal(list)  # Flow hotkey list
    EventItemChangedSignal = Signal(EventItem)

    WindowHandleUpdated = Signal(object)  # HWND
    CaptureImageReady = Signal(object)  # Image data
    MatchScoreUpdated = Signal(object)  # float OR (index:int, value:float)

    def __init__(self) -> None:
        super().__init__()
        self.EventItems: List[EventItem] = []
        self.TargetWindowService = TargetWindowService()
        self.InputAutomationService = InputAutomationService()
        self.StatePersistenceService = StatePersistenceService()
        self.EventEditingService = EventEditingService()
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

        self._selectedEventItem : Optional[EventItem] = None
        self._captureMousePositionNormalized: Optional[tuple[float, float]] = None
        
        self.StartSentinel()  # Initialize the sentinel monitoring

    def AddEvent(self) -> None:
        newAction = ActionItem()
        newEvent = EventItem(name="New Event", action=newAction)
        self.EventItems.append(newEvent)
        self.EventItemAddedSignal.emit(newEvent)

    def RemoveEvent(self) -> None:
        if self._selectedEventItem is None:
            return
        index = self.EventItems.index(self._selectedEventItem)
        if 0 <= index < len(self.EventItems):
            self.EventItems.pop(index)
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
        # Note: execution is performed by TriggerMonitorService (if a window handle is available).
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
        eventItem = self._selectedEventItem
        if not eventItem:
            return
        self.EventEditingService.UpdateEventName(eventItem, name)
        self.EventItemChangedSignal.emit(eventItem)

    def UpdateSelectedActivationType(self, activationType: ActivationType) -> None:
        eventItem = self._selectedEventItem
        if not eventItem:
            return
        self.EventEditingService.UpdateActivationType(eventItem, activationType)
        self.EventItemChangedSignal.emit(eventItem)

    def UpdateSelectedLoopCount(self, loopCount: int) -> None:
        eventItem = self._selectedEventItem
        if not eventItem:
            return
        self.EventEditingService.UpdateLoopCount(eventItem, loopCount)
        self.EventItemChangedSignal.emit(eventItem)

    def UpdateSelectedLoopIntervalMs(self, intervalMs: int) -> None:
        eventItem = self._selectedEventItem
        if not eventItem:
            return
        self.EventEditingService.UpdateLoopIntervalMs(eventItem, intervalMs)
        self.EventItemChangedSignal.emit(eventItem)

    def UpdateSelectedThreshold(self, threshold: float) -> None:
        eventItem = self._selectedEventItem
        if not eventItem:
            return
        self.EventEditingService.UpdateThreshold(eventItem, threshold)
        self.EventItemChangedSignal.emit(eventItem)

    def UpdateSelectedTriggerOnThresholdExceed(self, isEnabled: bool) -> None:
        eventItem = self._selectedEventItem
        if not eventItem:
            return
        self.EventEditingService.UpdateTriggerOnThresholdExceed(eventItem, isEnabled)
        self.EventItemChangedSignal.emit(eventItem)

    def UpdateSelectedRetriggerTimeMs(self, retriggerTimeMs: float) -> None:
        eventItem = self._selectedEventItem
        if not eventItem:
            return
        self.EventEditingService.UpdateRetriggerTimeMs(eventItem, retriggerTimeMs)
        self.EventItemChangedSignal.emit(eventItem)

    def UpdateSelectedActivationHotkey(self, virtualKeyCodes: List[int]) -> None:
        eventItem = self._selectedEventItem
        if not eventItem:
            return
        self.EventEditingService.UpdateActivationHotkey(eventItem, virtualKeyCodes)
        self.EventItemChangedSignal.emit(eventItem)

    def SetSelectedTemplateAndRoi(self, templateImage: np.ndarray[Any, Any], roi: RectangleRegion) -> None:
        eventItem = self._selectedEventItem
        if not eventItem:
            return
        self.EventEditingService.SetTemplateAndRoi(eventItem, templateImage, roi)
        self.EventItemChangedSignal.emit(eventItem)

    def AddSelectedMouseStepFromCapturedPosition(self) -> None:
        eventItem = self._selectedEventItem
        if not eventItem or not eventItem.AssignedAction:
            return
        if self._captureMousePositionNormalized is None:
            raise ValueError("No mouse position captured")
        normalizedX, normalizedY = self._captureMousePositionNormalized
        self.EventEditingService.AddMouseStep(eventItem, normalizedX, normalizedY)
        self.EventItemChangedSignal.emit(eventItem)

    def AddSelectedKeyboardStep(self, virtualKeyCode: Any) -> None:
        eventItem = self._selectedEventItem
        if not eventItem or not eventItem.AssignedAction:
            return

        self.EventEditingService.AddKeyboardStep(eventItem, virtualKeyCode)
        self.EventItemChangedSignal.emit(eventItem)

    def AddSelectedDelayStep(self, milliseconds: int) -> None:
        eventItem = self._selectedEventItem
        if not eventItem or not eventItem.AssignedAction:
            return
        self.EventEditingService.AddDelayStep(eventItem, milliseconds)
        self.EventItemChangedSignal.emit(eventItem)

    def RemoveSelectedStep(self, index: int) -> None:
        eventItem = self._selectedEventItem
        if not eventItem or not eventItem.AssignedAction:
            return
        self.EventEditingService.RemoveStep(eventItem, index)
        self.EventItemChangedSignal.emit(eventItem)

    def MoveSelectedStep(self, fromIndex: int, toIndex: int) -> None:
        eventItem = self._selectedEventItem
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
        return self._selectedEventItem

    @SelectedEventItem.setter
    def SelectedEventItem(self, event: Optional[EventItem]) -> None:        
        self._selectedEventItem = event
        self.EventItemSelectedSignal.emit(event)

    @property
    def CaptureMousePositionNormalized(self) -> Optional[tuple[float, float]]:
        return self._captureMousePositionNormalized
    
    @CaptureMousePositionNormalized.setter
    def CaptureMousePositionNormalized(self, point: Optional[tuple[float, float]]) -> None:
        self._captureMousePositionNormalized = point
