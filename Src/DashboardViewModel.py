import os
import pickle
from typing import (
    cast, List, Optional, Any, Dict
)
# Third-party imports
import numpy as np
from PySide6.QtCore import Signal, QObject

# Local imports
from Src.Helper import (
    SendKeystrokeToWindow, SendMouseClickToWindow,
    FindHwndByTitle, LaunchHwndByExecutable, ResizeWindow,
    FindPidByHwnd, KeyNameFromVk, VkFromKeyName
)
from Src.Models import (
    ActivationType, InputType, 
    ActionItem, EventItem, MacroStep, RectangleRegion
)

from Src.Engine.SentinelServices import TriggerMonitorService, LiveCaptureService

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
        self.CurrentWindowHandle: Optional[int] = None
        self.LiveThread: Optional[LiveCaptureService] = None
        self.LastLiveImage: Optional[np.ndarray[Any, Any]] = None
        self.TriggerThread: Optional[TriggerMonitorService] = None

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
        windowHandle = FindHwndByTitle(title)
        self.CurrentWindowHandle = windowHandle
        self.WindowHandleUpdated.emit(windowHandle)
        return windowHandle

    def GetPidByHwnd(self, windowHandle: int) -> Optional[int]:
        if not windowHandle:
            return None
        return FindPidByHwnd(windowHandle)

    def GetCurrentTargetPid(self) -> Optional[int]:
        if not self.CurrentWindowHandle:
            return None
        return FindPidByHwnd(self.CurrentWindowHandle)

    def HasTargetWindow(self) -> bool:
        return self.CurrentWindowHandle is not None

    def KeyNameFromVk(self, virtualKeyCode: int) -> str:
        return KeyNameFromVk(virtualKeyCode)

    def LaunchApplication(self, path: str) -> Optional[int]:
        if path:
            return LaunchHwndByExecutable(path)
        return None

    def ResizeTargetWindow(self, width: int, height: int) -> None:
        if self.CurrentWindowHandle:
            ResizeWindow(self.CurrentWindowHandle, width, height)

    def ToggleCapture(self, active: bool) -> None:
        if active and self.CurrentWindowHandle:
            self.StopCapture()
            self.LiveThread = LiveCaptureService(
                window_handle=self.CurrentWindowHandle,
                interval_ms=200,
                on_image=self._handleImageCaptured,
            )
            self.LiveThread.Start()
        else:
            self.StopCapture()

    def GetLastLiveImage(self) -> Optional[np.ndarray[Any, Any]]:
        return self.LastLiveImage

    def _handleImageCaptured(self, image: Optional[np.ndarray[Any, Any]]) -> None:
        self.LastLiveImage = image
        self.CaptureImageReady.emit(image)

        if self.TriggerThread is not None:
            self.TriggerThread.SetImage(image)

    def StopCapture(self) -> None:
        if self.LiveThread is not None:
            self.LiveThread.Stop()
            self.LiveThread = None

    def StartSentinel(self) -> None:
        if self.TriggerThread is not None:
            return

        self.TriggerThread = TriggerMonitorService(
            get_event_items=lambda: self.EventItems,
            poll_interval_ms=50,
            on_event_triggered=self._onEventTriggered,
            on_event_disabled=self.EventItemChangedSignal.emit,
            on_flow_state_changed=self.EventExecutionStateChangedSignal.emit,
            on_flow_hotkey_changed=self.EventExecutionStateHotkeyChangedSignal.emit,
            on_match_score_updated=self.MatchScoreUpdated.emit,
        )
        self.TriggerThread.Start()

    def StopSentinel(self) -> None:
        if self.TriggerThread is not None:
            self.TriggerThread.Stop()
            self.TriggerThread = None

    def _onEventTriggered(self, event: EventItem) -> None:
        print(f"Event Triggered: {event.Name}")

    def SaveState(self, filePath: str) -> None:
        try:
            flowHotkey = self.TriggerThread.GetFlowHotkey() if self.TriggerThread else []
            data_to_save: Dict[str, Any] = {
                "events": self.EventItems,
                "settings": flowHotkey,  # A second object
                "version": "1.0.0"
            }
            
            with open(filePath, 'wb') as file:
                pickle.dump(data_to_save, file)
                
            print(f"State successfully saved to {filePath}")
        except Exception as e:
            print(f"SaveState Error: {e}")
            raise e

    def LoadState(self, filePath: str) -> None:
        if not os.path.exists(filePath):
            return
            
        try:
            with open(filePath, 'rb') as file:
                data = pickle.load(file)
                
            # --- SMART LOADING LOGIC ---
            loadedEvents: List[EventItem] = []
            loadedHotkey: List[int] = []
            
            if isinstance(data, dict):
                # New Format: Dictionary containing events and settings
                dataDict: Dict[str, Any] = cast(Dict[str, Any], data)
                loadedEvents = cast(List[EventItem], dataDict.get("events", []))
                loadedHotkey = cast(List[int], dataDict.get("settings", []))
                print(f"Loading new format (v{dataDict.get('version', '1.0.0')})")
            else:
                print("Unknown data format in save file.")
                return
                
            # ---------------------------
            # Populate the UI/Model
            if self.TriggerThread is not None:
                self.TriggerThread.SetFlowEnabled(False)  # Ensure flow is off during loading
                
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
            if self.TriggerThread is not None:
                self.TriggerThread.SetFlowHotkey(loadedHotkey)
        except Exception as e:
            print(f"LoadState Error: {e}")
            raise e

    def ToggleSentinelFlow(self) -> None:
        if self.TriggerThread:
            self.TriggerThread.ToggleFlowEnabled()

    def SetSentinelFlowHotkey(self, virtualKeyCodes: List[int]) -> None:
        if self.TriggerThread is not None:
            self.TriggerThread.SetFlowHotkey(virtualKeyCodes)

    def SetEventEnabled(self, eventItem: EventItem, isEnabled: bool) -> None:
        eventItem.IsEnabled = isEnabled
        eventItem.ResetTransientState()
        self.EventItemChangedSignal.emit(eventItem)

    def UpdateSelectedEventName(self, name: str) -> None:
        eventItem = self._selectedEventItem
        if not eventItem:
            return
        eventItem.Name = name
        self.EventItemChangedSignal.emit(eventItem)

    def UpdateSelectedActivationType(self, activationType: ActivationType) -> None:
        eventItem = self._selectedEventItem
        if not eventItem:
            return
        eventItem.SelectedActivationType = activationType
        eventItem.ResetTransientState()
        self.EventItemChangedSignal.emit(eventItem)

    def UpdateSelectedLoopCount(self, loopCount: int) -> None:
        eventItem = self._selectedEventItem
        if not eventItem:
            return
        eventItem.LoopCount = loopCount
        self.EventItemChangedSignal.emit(eventItem)

    def UpdateSelectedLoopIntervalMs(self, intervalMs: int) -> None:
        eventItem = self._selectedEventItem
        if not eventItem:
            return
        eventItem.IntervalMilliseconds = intervalMs
        self.EventItemChangedSignal.emit(eventItem)

    def UpdateSelectedThreshold(self, threshold: float) -> None:
        eventItem = self._selectedEventItem
        if not eventItem:
            return
        eventItem.Threshold = threshold
        self.EventItemChangedSignal.emit(eventItem)

    def UpdateSelectedTriggerOnThresholdExceed(self, isEnabled: bool) -> None:
        eventItem = self._selectedEventItem
        if not eventItem:
            return
        eventItem.TriggerOnThresholdExceed = isEnabled
        self.EventItemChangedSignal.emit(eventItem)

    def UpdateSelectedRetriggerTimeMs(self, retriggerTimeMs: float) -> None:
        eventItem = self._selectedEventItem
        if not eventItem:
            return
        eventItem.RetriggerTimeMilliseconds = retriggerTimeMs
        self.EventItemChangedSignal.emit(eventItem)

    def UpdateSelectedActivationHotkey(self, virtualKeyCodes: List[int]) -> None:
        eventItem = self._selectedEventItem
        if not eventItem:
            return
        eventItem.ActivationVirtualKeyCodes = virtualKeyCodes
        self.EventItemChangedSignal.emit(eventItem)

    def SetSelectedTemplateAndRoi(self, templateImage: np.ndarray[Any, Any], roi: RectangleRegion) -> None:
        eventItem = self._selectedEventItem
        if not eventItem:
            return
        eventItem.TemplateImage = templateImage
        eventItem.Roi = roi
        self.EventItemChangedSignal.emit(eventItem)

    def AddSelectedMouseStepFromCapturedPosition(self) -> None:
        eventItem = self._selectedEventItem
        if not eventItem or not eventItem.AssignedAction:
            return
        if self._captureMousePositionNormalized is None:
            raise ValueError("No mouse position captured")
        normalizedX, normalizedY = self._captureMousePositionNormalized
        newStep = MacroStep(InputType.Mouse, (normalizedX, normalizedY), f"Click at ({normalizedX:.7f}, {normalizedY:.7f})")
        eventItem.AssignedAction.AddStep(newStep)
        self.EventItemChangedSignal.emit(eventItem)

    def AddSelectedKeyboardStep(self, virtualKeyCode: Any) -> None:
        eventItem = self._selectedEventItem
        if not eventItem or not eventItem.AssignedAction:
            return

        if isinstance(virtualKeyCode, (list, tuple)):
            seq = cast(list[int] | tuple[int, ...], virtualKeyCode)
            keys = [int(vk) for vk in seq]
            names = [KeyNameFromVk(vk) for vk in keys]
            description = f"Press \"{' + '.join(names)}\""
            newStep = MacroStep(InputType.Keyboard, keys, description)
        else:
            vk = int(virtualKeyCode)
            newStep = MacroStep(InputType.Keyboard, vk, f"Press \"{KeyNameFromVk(vk)}\"")

        eventItem.AssignedAction.AddStep(newStep)
        self.EventItemChangedSignal.emit(eventItem)

    def AddSelectedDelayStep(self, milliseconds: int) -> None:
        eventItem = self._selectedEventItem
        if not eventItem or not eventItem.AssignedAction:
            return
        newStep = MacroStep(InputType.Delay, milliseconds, f"Wait {milliseconds}ms")
        eventItem.AssignedAction.AddStep(newStep)
        self.EventItemChangedSignal.emit(eventItem)

    def RemoveSelectedStep(self, index: int) -> None:
        eventItem = self._selectedEventItem
        if not eventItem or not eventItem.AssignedAction:
            return
        eventItem.AssignedAction.RemoveStep(index)
        self.EventItemChangedSignal.emit(eventItem)

    def MoveSelectedStep(self, fromIndex: int, toIndex: int) -> None:
        eventItem = self._selectedEventItem
        if not eventItem or not eventItem.AssignedAction:
            return
        steps = eventItem.AssignedAction.MacroSteps
        if fromIndex < 0 or fromIndex >= len(steps) or toIndex < 0 or toIndex >= len(steps):
            return
        steps[fromIndex], steps[toIndex] = steps[toIndex], steps[fromIndex]
        self.EventItemChangedSignal.emit(eventItem)

    def TrySendMouseClick(self, normalizedX: float, normalizedY: float) -> bool:
        if not self.CurrentWindowHandle:
            return False
        SendMouseClickToWindow(self.CurrentWindowHandle, normalizedX, normalizedY)
        return True

    def TrySendKeystrokeByName(self, keyName: str) -> bool:
        if not self.CurrentWindowHandle:
            return False
        virtualKeyCode = VkFromKeyName(keyName)
        if not virtualKeyCode:
            return False
        SendKeystrokeToWindow(self.CurrentWindowHandle, virtualKeyCode)
        return True

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
