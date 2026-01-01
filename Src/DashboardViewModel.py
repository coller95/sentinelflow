import os
import time
import pickle
from typing import (
    cast, List, Optional, Any, Dict
)
# Third-party imports
import numpy as np
from PySide6.QtCore import (
    Signal, QThread, QObject,
    QMutex, QMutexLocker
)

# Local imports
from Src.Helper import (
    SendKeystrokeToWindow, SendMouseClickToWindow, CaptureWindowByHwnd,
    FindHwndByTitle, LaunchHwndByExecutable, ResizeWindow, IsHotkeyActive,
    FindPidByHwnd, KeyNameFromVk, VkFromKeyName
)
from Src.Models import (
    ActivationType, InputType, 
    ActionItem, EventItem, MacroStep, RectangleRegion
)
from Engine.ActivationEngine import ActivationEngine


class TriggerMonitorThread(QThread):
    """Thread responsible for monitoring trigger conditions and executing actions."""

    EventTriggered = Signal(EventItem)
    EventDisabled = Signal(EventItem)
    FlowStateChanged = Signal(bool)
    FlowHotkeyChanged = Signal(list)
    MatchScoreUpdated = Signal(object)  # float OR (index:int, value:float)

    def __init__(self, viewModel: "DashboardViewModel", pollIntervalMs: int = 50) -> None:
        """
        Initialize the trigger monitor thread.
        
        Args:
            viewModel: Reference to the dashboard view model
            pollIntervalMs: Polling interval in milliseconds
        """
        super().__init__()
        self._viewModel: DashboardViewModel = viewModel
        self._pollIntervalMs: int = pollIntervalMs
        self._isRunning: bool = True
        # Image injection handling
        self._imageMutex: QMutex = QMutex()
        self._currentImage: Optional[np.ndarray[Any, Any]] = None
        # Flow control
        self._flowEnabled: bool = True
        self._flowHotkeyVirtualKeyCodes: List[int] = []
        self._flowHotkeyIsCurrentlyHeld: bool = False
        self._engine = ActivationEngine()

    def SetImage(self, image: Optional[np.ndarray[Any, Any]]) -> None:
        """
        Set the current image for processing.
        
        Args:
            image: Image data to process
        """
        with QMutexLocker(self._imageMutex):
            self._currentImage = image

    def SetFlowEnabled(self, isEnabled: bool) -> None:
        """
        Set the flow state directly.
        
        Args:
            isEnabled: New flow state
        """
        self._flowEnabled = isEnabled
        self.FlowStateChanged.emit(self._flowEnabled)

    def ToggleFlowEnabled(self) -> None:
        """Toggle the flow state."""
        self.SetFlowEnabled(not self._flowEnabled)

    def SetFlowHotkey(self, virtualKeyCodes: List[int]) -> None:
        """
        Set the hotkey to toggle flow state.
        
        Args:
            virtualKeyCodes: List of virtual key codes
        """
        self._flowHotkeyVirtualKeyCodes = virtualKeyCodes
        print(f"Flow hotkey set to: {virtualKeyCodes}")
        self.FlowHotkeyChanged.emit(virtualKeyCodes)

    def GetFlowHotkey(self) -> List[int]:
        """Get the current flow hotkey virtual key codes."""
        return self._flowHotkeyVirtualKeyCodes

    def run(self) -> None:
        """Main thread execution loop."""
        while self._isRunning:
            # Check flow hotkey (only if configured)
            if self._flowHotkeyVirtualKeyCodes:
                isDownNow = IsHotkeyActive(self._flowHotkeyVirtualKeyCodes)
                if self._flowHotkeyIsCurrentlyHeld and not isDownNow:
                    self.ToggleFlowEnabled()
                self._flowHotkeyIsCurrentlyHeld = isDownNow
            else:
                self._flowHotkeyIsCurrentlyHeld = False

            if not self._flowEnabled:
                time.sleep(self._pollIntervalMs / 1000.0)
                continue

            # Copy image for processing
            localImage: Optional[np.ndarray[Any, Any]] = None
            with QMutexLocker(self._imageMutex):
                localImage = self._currentImage
                self._currentImage = None

            # Iterate over a snapshot to avoid concurrent-modification issues
            eventItemsSnapshot = list(self._viewModel.EventItems)

            result = self._engine.evaluate(eventItemsSnapshot, localImage)

            for event in result.triggered:
                self.EventTriggered.emit(event)

            for event in result.disabled:
                self.EventDisabled.emit(event)

            for matchUpdate in result.match_updates:
                self.MatchScoreUpdated.emit(matchUpdate)
            
            time.sleep(self._pollIntervalMs / 1000.0)

    def Stop(self) -> None:
        """Stop the thread execution."""
        self._isRunning = False
        self.wait()


class LiveCaptureThread(QThread):
    """
    Captures screenshots of the target window at regular intervals.
    
    Signals:
        ImageCaptured: Emitted when an image is captured
    """
    ImageCaptured = Signal(object)  # Image data

    def __init__(self, windowHandle: int, intervalMs: int = 200, parent: Optional[QObject] = None) -> None:
        """
        Initialize the live capture thread.
        
        Args:
            windowHandle: Window handle to capture
            intervalMs: Capture interval in milliseconds
            parent: Parent QObject
        """
        super().__init__(parent)
        self.WindowHandle: int = windowHandle
        self.IntervalMs: int = intervalMs
        self._isRunning: bool = True
        self._imageCount: int = 0

    def run(self) -> None:
        """Main thread execution loop."""
        self._isRunning = True
        while self._isRunning:
            try:
                image = CaptureWindowByHwnd(self.WindowHandle)
                self.ImageCaptured.emit(image)
            except Exception as e:
                print(f"Live capture error: {e}")
                self.ImageCaptured.emit(None)
                self._isRunning = False
                
            time.sleep(self.IntervalMs / 1000.0)

    def Stop(self) -> None:
        """Stop the thread execution."""
        self._isRunning = False
        self.wait()


class DashboardViewModel(QObject):
    """
    Handles the business logic and state management for the dashboard.
    
    Signals:
        EventAdded: Emitted when an event is added
        EventRemoved: Emitted when an event is removed
        WindowHandleUpdated: Emitted when the window handle is updated
        CaptureImageReady: Emitted when a capture image is ready
        EventDisabled: Emitted when an event is disabled
        FlowStateChanged: Emitted when the flow state changes
        FlowHotkeyChanged: Emitted when the flow hotkey changes
        MatchScoreUpdated: Emitted when a match score is updated
    """
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
        """Initialize the dashboard view model."""
        super().__init__()
        self.EventItems: List[EventItem] = []
        self.CurrentWindowHandle: Optional[int] = None
        self.LiveThread: Optional[LiveCaptureThread] = None
        self.LastLiveImage: Optional[np.ndarray[Any, Any]] = None
        self.TriggerThread: Optional[TriggerMonitorThread] = None

        self._selectedEventItem : Optional[EventItem] = None
        self._captureMousePositionNormalized: Optional[tuple[float, float]] = None
        
        self.StartSentinel()  # Initialize the sentinel monitoring

    def AddEvent(self) -> None:
        """Add a new event to the model."""
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
        """
        Find a window by its title.
        
        Args:
            title: Title of the window to find
            
        Returns:
            Window handle if found, None otherwise
        """
        windowHandle = FindHwndByTitle(title)
        self.CurrentWindowHandle = windowHandle
        self.WindowHandleUpdated.emit(windowHandle)
        return windowHandle

    def GetPidByHwnd(self, windowHandle: int) -> Optional[int]:
        if not windowHandle:
            return None
        return FindPidByHwnd(windowHandle)

    def GetCurrentTargetPid(self) -> Optional[int]:
        """Get the PID for the currently selected target window (if any)."""
        if not self.CurrentWindowHandle:
            return None
        return FindPidByHwnd(self.CurrentWindowHandle)

    def HasTargetWindow(self) -> bool:
        """Return True if a target window is currently selected."""
        return self.CurrentWindowHandle is not None

    def KeyNameFromVk(self, virtualKeyCode: int) -> str:
        return KeyNameFromVk(virtualKeyCode)

    def LaunchApplication(self, path: str) -> Optional[int]:
        """
        Launch an application from the specified path.
        
        Args:
            path: Path to the executable
            
        Returns:
            Process ID if launched successfully, None otherwise
        """
        if path:
            return LaunchHwndByExecutable(path)
        return None

    def ResizeTargetWindow(self, width: int, height: int) -> None:
        """
        Resize the target window to the specified dimensions.
        
        Args:
            width: New width in pixels
            height: New height in pixels
        """
        if self.CurrentWindowHandle:
            ResizeWindow(self.CurrentWindowHandle, width, height)

    def ToggleCapture(self, active: bool) -> None:
        """
        Toggle live capture on or off.
        
        Args:
            active: True to start capture, False to stop
        """
        if active and self.CurrentWindowHandle:
            self.StopCapture()
            self.LiveThread = LiveCaptureThread(self.CurrentWindowHandle)
            self.LiveThread.ImageCaptured.connect(self._handleImageCaptured)
            
            if self.TriggerThread is not None:
                self.LiveThread.ImageCaptured.connect(self.TriggerThread.SetImage)
                
            self.LiveThread.start()
        else:
            self.StopCapture()

    def GetLastLiveImage(self) -> Optional[np.ndarray[Any, Any]]:
        """Get the most recently captured image (read-only access for the View)."""
        return self.LastLiveImage

    def _handleImageCaptured(self, image: Optional[np.ndarray[Any, Any]]) -> None:
        """
        Handle a captured image.
        
        Args:
            image: Captured image data
        """
        self.LastLiveImage = image
        self.CaptureImageReady.emit(image)

    def StopCapture(self) -> None:
        """Stop the live capture thread."""
        if self.LiveThread:
            self.LiveThread.Stop()

            # Disconnect only the connections we created (typed-safe).
            try:
                self.LiveThread.ImageCaptured.disconnect(self._handleImageCaptured)
            except (RuntimeError, TypeError):
                pass

            if self.TriggerThread is not None:
                try:
                    self.LiveThread.ImageCaptured.disconnect(self.TriggerThread.SetImage)
                except (RuntimeError, TypeError):
                    pass

            self.LiveThread.wait()
            self.LiveThread = None

    def StartSentinel(self) -> None:
        """Start the sentinel monitoring thread."""
        if not self.TriggerThread:
            self.TriggerThread = TriggerMonitorThread(self)
            self.TriggerThread.EventTriggered.connect(self._onEventTriggered)
            self.TriggerThread.EventDisabled.connect(self.EventItemChangedSignal)
            self.TriggerThread.FlowStateChanged.connect(self.EventExecutionStateChangedSignal)
            self.TriggerThread.FlowHotkeyChanged.connect(self.EventExecutionStateHotkeyChangedSignal)
            self.TriggerThread.MatchScoreUpdated.connect(self.MatchScoreUpdated)
            self.TriggerThread.start()

    def _onEventTriggered(self, event: EventItem) -> None:
        """
        Handle an event trigger.
        
        Args:
            event: Event that was triggered
        """
        print(f"Event Triggered: {event.Name}")
        if self.CurrentWindowHandle:
            event.Trigger(self.CurrentWindowHandle)

    def SaveState(self, filePath: str) -> None:
        """
        Save the current state to a file.
        
        Args:
            filePath: Path to save the state to
        """
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
        """
        Load state from a file.
        
        Args:
            filePath: Path to load the state from
        """
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
        """Toggle the sentinel flow state."""
        if self.TriggerThread:
            self.TriggerThread.ToggleFlowEnabled()

    def SetSentinelFlowHotkey(self, virtualKeyCodes: List[int]) -> None:
        """Set the global flow hotkey (encapsulates TriggerThread access)."""
        if self.TriggerThread is not None:
            self.TriggerThread.SetFlowHotkey(virtualKeyCodes)

    def SetEventEnabled(self, eventItem: EventItem, isEnabled: bool) -> None:
        """Enable/disable an event and reset transient counters."""
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

    def AddSelectedKeyboardStep(self, virtualKeyCode: int) -> None:
        eventItem = self._selectedEventItem
        if not eventItem or not eventItem.AssignedAction:
            return
        newStep = MacroStep(InputType.Keyboard, virtualKeyCode, f"Press \"{KeyNameFromVk(virtualKeyCode)}\"")
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

    def StopSentinel(self) -> None:
        """Stop the trigger monitoring thread."""
        if self.TriggerThread:
            self.TriggerThread.Stop()

            # Disconnect only the connections we created (typed-safe).
            try:
                self.TriggerThread.EventTriggered.disconnect(self._onEventTriggered)
            except (RuntimeError, TypeError):
                pass
            try:
                self.TriggerThread.EventDisabled.disconnect(self.EventItemChangedSignal)
            except (RuntimeError, TypeError):
                pass
            try:
                self.TriggerThread.FlowStateChanged.disconnect(self.EventExecutionStateChangedSignal)
            except (RuntimeError, TypeError):
                pass
            try:
                self.TriggerThread.FlowHotkeyChanged.disconnect(self.EventExecutionStateHotkeyChangedSignal)
            except (RuntimeError, TypeError):
                pass
            try:
                self.TriggerThread.MatchScoreUpdated.disconnect(self.MatchScoreUpdated)
            except (RuntimeError, TypeError):
                pass

            self.TriggerThread = None

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
