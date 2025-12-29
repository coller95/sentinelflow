"""
SentinelFlow Main Dashboard
Description: PySide6 GUI application for window automation using MVVM pattern.
Author: SentinelFlow Team
Version: 1.0.0
"""
# pylint: disable=too-many-lines
# =============================================================================
# IMPORTS
# =============================================================================
# Standard library imports
import os
import sys
import time
import pickle
from enum import Enum, auto
from typing import (
    cast, List, Optional, Any, Callable, Dict, Final
)
# Third-party imports
import numpy as np
import cv2
from PySide6.QtCore import (
    Signal, QThread, Qt, QPoint, QObject, QSize, QRect,
    QMutex, QMutexLocker
)
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QFileDialog, QListWidget, QMessageBox,
    QSizePolicy, QListWidgetItem, QComboBox, QGroupBox,
    QDialog, QInputDialog, QRubberBand, QCheckBox
)
from PySide6.QtGui import (
    QPainter, QPen, QImage, QPixmap, QIcon, QKeyEvent,
    QMouseEvent, QPaintEvent, QResizeEvent, QCloseEvent
)
# Local imports
from Src.Helper import (
    SendKeystrokeToWindow, SendMouseClickToWindow, CaptureWindowByHwnd,
    FindHwndByTitle, LaunchHwndByExecutable, ResizeWindow, IsHotkeyActive,
    KeyNameFromVk, VkFromKeyName, CropImage, MatchTemplate,
    EstimateProgressBarPercentage, FindPidByHwnd
)
# =============================================================================
# CONSTANTS AND GLOBAL CONFIGURATION
# =============================================================================
# High DPI Scaling setup
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
# UI styling constants
BUTTON_STYLE_RUNNING: Final[str] = """
QPushButton {
    background-color: #c0392b; /* Darker Red */
    color: white;
    border-radius: 6px;
    font-weight: bold;
    padding: 8px;
}
QPushButton:hover {
    background-color: #e74c3c; /* Brighter Red */
}
"""
BUTTON_STYLE_STOPPED: Final[str] = """
QPushButton {
    background-color: #27ae60; /* Darker Green */
    color: white;
    border-radius: 6px;
    font-weight: bold;
    padding: 8px;
}
QPushButton:hover {
    background-color: #2ecc71; /* Brighter Green */
}
"""
# =============================================================================
# ENUMERATIONS
# =============================================================================
class ActivationType(Enum):
    """Types of event activation mechanisms."""
    NotSet = auto()
    Hotkey = auto()
    Loop = auto()
    ImageMatchRoi = auto()
    ProgessBar = auto()

class InputType(Enum):
    """Types of macro input steps."""
    Mouse = auto()
    Keyboard = auto()
    Delay = auto()
# =============================================================================
# MODEL CLASSES
# =============================================================================
class RectangleRegion:
    """Represents a normalized rectangle region within a window."""
    
    def __init__(self, xNormalized: float = 0.0, yNormalized: float = 0.0, 
                 widthNormalized: float = 1.0, heightNormalized: float = 1.0) -> None:
        """
        Initialize a normalized rectangle region.
        
        Args:
            xNormalized: Normalized X coordinate (0.0 to 1.0)
            yNormalized: Normalized Y coordinate (0.0 to 1.0)
            widthNormalized: Normalized width (0.0 to 1.0)
            heightNormalized: Normalized height (0.0 to 1.0)
        """
        self._xNormalized: float = xNormalized
        self._yNormalized: float = yNormalized
        self._widthNormalized: float = widthNormalized
        self._heightNormalized: float = heightNormalized

    @property
    def XNormalized(self) -> float:
        """Get the normalized X coordinate."""
        return self._xNormalized
        
    @XNormalized.setter
    def XNormalized(self, value: float) -> None:
        """Set the normalized X coordinate."""
        self._xNormalized = value

    @property
    def YNormalized(self) -> float:
        """Get the normalized Y coordinate."""
        return self._yNormalized
        
    @YNormalized.setter
    def YNormalized(self, value: float) -> None:
        """Set the normalized Y coordinate."""
        self._yNormalized = value

    @property
    def WidthNormalized(self) -> float:
        """Get the normalized width."""
        return self._widthNormalized
        
    @WidthNormalized.setter
    def WidthNormalized(self, value: float) -> None:
        """Set the normalized width."""
        self._widthNormalized = value

    @property
    def HeightNormalized(self) -> float:
        """Get the normalized height."""
        return self._heightNormalized
        
    @HeightNormalized.setter
    def HeightNormalized(self, value: float) -> None:
        """Set the normalized height."""
        self._heightNormalized = value


class MacroStep:
    """Represents a single step in a macro sequence."""
    
    def __init__(self, inputType: InputType, value: Any = None, description: str = "") -> None:
        """
        Initialize a macro step.
        
        Args:
            inputType: Type of input (Mouse, Keyboard, Delay)
            value: Value specific to the input type
            description: Human-readable description of the step
        """
        self._inputType: InputType = inputType
        self._value: Any = value
        self._description: str = description

    @property
    def Description(self) -> str:
        """Get the description of this macro step."""
        return self._description
        
    @Description.setter
    def Description(self, value: str) -> None:
        """Set the description of this macro step."""
        self._description = value

    @property
    def InputType(self) -> InputType:
        """Get the input type of this macro step."""
        return self._inputType

    @property
    def Value(self) -> Any:
        """Get the value of this macro step."""
        return self._value

    def Execute(self, windowHandle: int) -> None:
        """
        Execute this macro step on the specified window.
        
        Args:
            windowHandle: Handle to the target window
        """
        if self._inputType == InputType.Keyboard:
            self._sendKeystroke(windowHandle, self._value)
        elif self._inputType == InputType.Mouse:
            # self._value is expected to be a tuple (xNormalized, yNormalized)
            self._sendMouseClick(windowHandle, self._value[0], self._value[1])
        elif self._inputType == InputType.Delay:
            # self._value is milliseconds
            time.sleep(self._value / 1000.0)

    def _sendKeystroke(self, hwnd: int, virtualKeyCode: int) -> None:
        """
        Send a keyboard keystroke to the specified window.
        
        Args:
            hwnd: Window handle
            virtualKeyCode: Virtual key code
        """
        SendKeystrokeToWindow(hwnd, virtualKeyCode)

    def _sendMouseClick(self, hwnd: int, xNormalized: float, yNormalized: float) -> None:
        """
        Send a mouse click to normalized coordinates in the specified window.
        
        Args:
            hwnd: Window handle
            xNormalized: Normalized X coordinate (0.0 to 1.0)
            yNormalized: Normalized Y coordinate (0.0 to 1.0)
        """
        SendMouseClickToWindow(hwnd, xNormalized, yNormalized)


class ActionItem:
    """Represents a collection of macro steps that form an action."""
    
    def __init__(self) -> None:
        """Initialize an empty action item."""
        self._macroSteps: List[MacroStep] = []

    @property
    def MacroSteps(self) -> List[MacroStep]:
        """Get the list of macro steps in this action."""
        return self._macroSteps

    def AddStep(self, macroStep: MacroStep) -> None:
        """
        Add a macro step to this action.
        
        Args:
            macroStep: Step to add
        """
        self._macroSteps.append(macroStep)

    def RemoveStep(self, index: int) -> None:
        """
        Remove a macro step at the specified index.
        
        Args:
            index: Index of the step to remove
        """
        if 0 <= index < len(self._macroSteps):
            self._macroSteps.pop(index)

    def Execute(self, windowHandle: int) -> None:
        """
        Execute all macro steps in this action on the specified window.
        
        Args:
            windowHandle: Handle to the target window
        """
        if not self._macroSteps:
            return
            
        for step in self._macroSteps:
            step.Execute(windowHandle)


class EventItem:
    """Represents an event that triggers an action based on specific conditions."""
    
    def __init__(
        self,
        name: str,
        action: ActionItem,
        enabled: bool = False,
        activationType: ActivationType = ActivationType.NotSet,
        loopCount: int = 0,
        intervalMilliseconds: int = 1000,
        roi: RectangleRegion = RectangleRegion(0.0, 0.0, 1.0, 1.0),
        threshold: float = 0.99,
        retriggerTimeMilliseconds: float = 2000
    ) -> None:
        """
        Initialize an event item.
        
        Args:
            name: Name of the event
            action: Action to execute when triggered
            enabled: Whether the event is active
            activationType: Type of activation mechanism
            loopCount: Number of times to loop (0 = infinite, -1 = disabled)
            intervalMilliseconds: Interval between loop executions in milliseconds
            roi: Region of interest for image matching
            threshold: Threshold for image matching or progress bar
        """
        self._name: str = name
        self._enabled: bool = enabled
        self._selectedActivationType: ActivationType = activationType
        self._activationVirtualKeyCodes: List[int] = []
        self._isCurrentlyHeld: bool = False
        self._loopCount: int = loopCount
        self._loopCounter: int = 0
        self._intervalMilliseconds: int = intervalMilliseconds
        self._timeOfLastTriggerMilliseconds: float = 0.0
        self._roi: RectangleRegion = roi
        self._threshold: float = threshold
        self._triggerOnThresholdExceed: bool = True
        self._retriggerTimeMilliseconds: float = retriggerTimeMilliseconds
        self._matchScore: float = 0.0
        self._templateImage: Optional[np.ndarray[Any, Any]] = None
        self._percentFilled: float = 0.0
        self._assignedAction: ActionItem = action

    @property
    def Name(self) -> str:
        """Get the name of this event."""
        return self._name
        
    @Name.setter
    def Name(self, value: str) -> None:
        """Set the name of this event."""
        self._name = value

    @property
    def IsEnabled(self) -> bool:
        """Get whether this event is enabled."""
        return self._enabled
        
    @IsEnabled.setter
    def IsEnabled(self, value: bool) -> None:
        """Set whether this event is enabled."""
        self._enabled = value

    @property
    def SelectedActivationType(self) -> ActivationType:
        """Get the activation type for this event."""
        return self._selectedActivationType
        
    @SelectedActivationType.setter
    def SelectedActivationType(self, value: ActivationType) -> None:
        """Set the activation type for this event."""
        self._selectedActivationType = value

    @property
    def ActivationVirtualKeyCodes(self) -> List[int]:
        """Get the list of virtual key codes for hotkey activation."""
        return self._activationVirtualKeyCodes
        
    @ActivationVirtualKeyCodes.setter
    def ActivationVirtualKeyCodes(self, value: List[int]) -> None:
        """Set the list of virtual key codes for hotkey activation."""
        self._activationVirtualKeyCodes = value

    @property
    def IsCurrentlyHeld(self) -> bool:
        """Get the current state of hotkey activation."""
        return self._isCurrentlyHeld
        
    @IsCurrentlyHeld.setter
    def IsCurrentlyHeld(self, value: bool) -> None:
        """Set the current state of hotkey activation."""
        self._isCurrentlyHeld = value

    @property
    def LoopCount(self) -> int:
        """Get the number of times to loop."""
        return self._loopCount
        
    @LoopCount.setter
    def LoopCount(self, value: int) -> None:
        """Set the number of times to loop."""
        self._loopCount = value

    @property
    def LoopCounter(self) -> int:
        """Get the current loop iteration count."""
        return self._loopCounter
        
    @LoopCounter.setter
    def LoopCounter(self, value: int) -> None:
        """Set the current loop iteration count."""
        self._loopCounter = value

    @property
    def IntervalMilliseconds(self) -> int:
        """Get the interval between loop executions in milliseconds."""
        return self._intervalMilliseconds
        
    @IntervalMilliseconds.setter
    def IntervalMilliseconds(self, value: int) -> None:
        """Set the interval between loop executions in milliseconds."""
        self._intervalMilliseconds = value

    @property
    def TimeOfLastTriggerMilliseconds(self) -> float:
        """Get the timestamp of last trigger in milliseconds."""
        return self._timeOfLastTriggerMilliseconds
        
    @TimeOfLastTriggerMilliseconds.setter
    def TimeOfLastTriggerMilliseconds(self, value: float) -> None:
        """Set the timestamp of last trigger in milliseconds."""
        self._timeOfLastTriggerMilliseconds = value

    @property
    def Roi(self) -> RectangleRegion:
        """Get the region of interest for image matching."""
        return self._roi
        
    @Roi.setter
    def Roi(self, value: RectangleRegion) -> None:
        """Set the region of interest for image matching."""
        self._roi = value

    @property
    def TemplateImage(self) -> Optional[np.ndarray[Any, Any]]:
        """Get the template image for image matching."""
        return self._templateImage
        
    @TemplateImage.setter
    def TemplateImage(self, value: Optional[np.ndarray[Any, Any]]) -> None:
        """Set the template image for image matching."""
        self._templateImage = value

    @property
    def Threshold(self) -> float:
        """Get the threshold for image matching or progress bar."""
        return self._threshold
        
    @Threshold.setter
    def Threshold(self, value: float) -> None:
        """Set the threshold for image matching or progress bar."""
        self._threshold = value

    @property
    def TriggerOnThresholdExceed(self) -> bool:
        """Get whether to trigger when ThresholdExceed."""
        return self._triggerOnThresholdExceed
        
    @TriggerOnThresholdExceed.setter
    def TriggerOnThresholdExceed(self, value: bool) -> None:
        """Set whether to trigger when ThresholdExceed."""
        self._triggerOnThresholdExceed = value

    @property
    def RetriggerTimeMilliseconds(self) -> float:
        """Get the retrigger time in milliseconds."""
        return self._retriggerTimeMilliseconds
    
    @RetriggerTimeMilliseconds.setter
    def RetriggerTimeMilliseconds(self, value: float) -> None:
        """Set the retrigger time in milliseconds."""
        self._retriggerTimeMilliseconds = value

    @property
    def MatchScore(self) -> float:
        """Get the last match score from image matching."""
        return self._matchScore
        
    @MatchScore.setter
    def MatchScore(self, value: float) -> None:
        """Set the last match score from image matching."""
        self._matchScore = value

    @property
    def PercentFilled(self) -> float:
        """Get the last percentage filled from progress bar detection."""
        return self._percentFilled
        
    @PercentFilled.setter
    def PercentFilled(self, value: float) -> None:
        """Set the last percentage filled from progress bar detection."""
        self._percentFilled = value

    @property
    def AssignedAction(self) -> ActionItem:
        """Get the action assigned to this event."""
        return self._assignedAction
        
    @AssignedAction.setter
    def AssignedAction(self, value: ActionItem) -> None:
        """Set the action assigned to this event."""
        self._assignedAction = value

    def Trigger(self, windowHandle: int) -> None:
        """
        Trigger the event's assigned action on the specified window.
        
        Args:
            windowHandle: Handle to the target window
        """
        if self._enabled and self._assignedAction:
            self._assignedAction.Execute(windowHandle)
# =============================================================================
# VIEWMODEL CLASSES
# =============================================================================
class TriggerMonitorThread(QThread):
    """Thread responsible for monitoring trigger conditions and executing actions."""
    
    EventTriggered = Signal(EventItem)
    EventDisabled = Signal(EventItem)
    FlowStateChanged = Signal(bool)
    FlowHotkeyChanged = Signal(list)
    MatchScoreUpdated = Signal(float)  # score

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
            # Check flow hotkey
            isDownNow = IsHotkeyActive(self._flowHotkeyVirtualKeyCodes)
            if self._flowHotkeyIsCurrentlyHeld and not isDownNow:
                self.ToggleFlowEnabled()
            self._flowHotkeyIsCurrentlyHeld = isDownNow
            
            if not self._flowEnabled:
                time.sleep(self._pollIntervalMs / 1000.0)
                continue
                
            # Copy image for processing
            localImage: Optional[np.ndarray[Any, Any]] = None
            with QMutexLocker(self._imageMutex):
                localImage = self._currentImage
                self._currentImage = None

            # Process each event
            for index, event in enumerate(self._viewModel.EventItems):
                if not event.IsEnabled:
                    continue
                    
                if event.SelectedActivationType == ActivationType.Hotkey:
                    if len(event.ActivationVirtualKeyCodes) == 0:
                        continue
                        
                    isDownNow = IsHotkeyActive(event.ActivationVirtualKeyCodes)
                    if event.IsCurrentlyHeld and not isDownNow:
                        self.EventTriggered.emit(event)
                    event.IsCurrentlyHeld = isDownNow
                    
                elif event.SelectedActivationType == ActivationType.Loop:
                    if event.LoopCount < 0:
                        continue
                    elif event.LoopCount > 0:
                        if event.LoopCounter >= event.LoopCount:
                            event.IsEnabled = False
                            self.EventDisabled.emit(event)
                            
                    # Handle loop timing
                    if time.time() * 1000 - event.TimeOfLastTriggerMilliseconds < event.IntervalMilliseconds:
                        continue
                        
                    event.LoopCounter += 1
                    event.TimeOfLastTriggerMilliseconds = time.time() * 1000
                    self.EventTriggered.emit(event)
                    
                elif event.SelectedActivationType == ActivationType.ImageMatchRoi:
                    if localImage is None or event.TemplateImage is None:
                        continue
                        
                    localImageRoi = CropImage(localImage, (
                        event.Roi.XNormalized, 
                        event.Roi.YNormalized, 
                        event.Roi.WidthNormalized, 
                        event.Roi.HeightNormalized
                    ))
                    
                    event.MatchScore = MatchTemplate(localImageRoi, event.TemplateImage)
                    self.MatchScoreUpdated.emit(event.MatchScore)
                    
                    if event.TriggerOnThresholdExceed:
                        isConditionMet = event.MatchScore >= event.Threshold
                    else:
                        isConditionMet = event.MatchScore < event.Threshold
                        
                    currentTimeMs = int(time.time() * 1000)
                    timeSinceLastTrigger = currentTimeMs - event.TimeOfLastTriggerMilliseconds

                    # Logic Gates
                    isRisingEdge = isConditionMet and not event.IsCurrentlyHeld
                    isRetrigger = isConditionMet and (timeSinceLastTrigger > event.RetriggerTimeMilliseconds)

                    if isRisingEdge or isRetrigger:
                        self.EventTriggered.emit(event)
                        event.TimeOfLastTriggerMilliseconds = currentTimeMs

                    # Sync state
                    event.IsCurrentlyHeld = isConditionMet
                        
                elif event.SelectedActivationType == ActivationType.ProgessBar:
                    if localImage is None:
                        continue
                        
                    localImageRoi = CropImage(localImage, (
                        event.Roi.XNormalized, 
                        event.Roi.YNormalized, 
                        event.Roi.WidthNormalized, 
                        event.Roi.HeightNormalized
                    ))
                    
                    event.PercentFilled = EstimateProgressBarPercentage(localImageRoi)
                    self.MatchScoreUpdated.emit((index, event.PercentFilled))

                    
                    if event.TriggerOnThresholdExceed:
                        isConditionMet = event.PercentFilled >= event.Threshold
                    else:
                        isConditionMet = event.PercentFilled < event.Threshold
                        
                    currentTimeMs = int(time.time() * 1000)
                    timeSinceLastTrigger = currentTimeMs - event.TimeOfLastTriggerMilliseconds

                    # Logic Gates
                    isRisingEdge = isConditionMet and not event.IsCurrentlyHeld
                    isRetrigger = isConditionMet and (timeSinceLastTrigger > event.RetriggerTimeMilliseconds)

                    if isRisingEdge or isRetrigger:
                        self.EventTriggered.emit(event)
                        event.TimeOfLastTriggerMilliseconds = currentTimeMs

                    # Sync state
                    event.IsCurrentlyHeld = isConditionMet
            
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
    CaptureImageReady = Signal(object)  # Image data\
    MatchScoreUpdated = Signal(float)  # score

    def __init__(self) -> None:
        """Initialize the dashboard view model."""
        super().__init__()
        self.EventItems: List[EventItem] = []
        self.CurrentWindowHandle: Optional[int] = None
        self.LiveThread: Optional[LiveCaptureThread] = None
        self.LastLiveImage: Optional[np.ndarray[Any, Any]] = None
        self.TriggerThread: Optional[TriggerMonitorThread] = None

        self._selectedEventItem : Optional[EventItem] = None
        
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

    def _handleImageCaptured(self, image: np.ndarray[Any, Any]) -> None:
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
            try:
                self.LiveThread.ImageCaptured.disconnect()
            except RuntimeError:
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
                self.EventItems.append(event)
            if hasattr(self, 'EventAdded') and loadedEvents:
                self.EventItemAddedSignal.emit(loadedEvents[-1])
                
            # Apply settings if they exist
            if self.TriggerThread and loadedHotkey:
                self.TriggerThread.SetFlowHotkey(loadedHotkey)
        except Exception as e:
            print(f"LoadState Error: {e}")
            raise e

    def ToggleSentinelFlow(self) -> None:
        """Toggle the sentinel flow state."""
        if self.TriggerThread:
            self.TriggerThread.ToggleFlowEnabled()

    @property
    def SelectedEventItem(self) -> Optional[EventItem]:\
        return self._selectedEventItem
    
    @SelectedEventItem.setter
    def SelectedEventItem(self, event: Optional[EventItem]) -> None:        
        self._selectedEventItem = event
        self.EventItemSelectedSignal.emit(event)



# =============================================================================
# VIEW CLASSES
# =============================================================================
class ClickableImageLabel(QLabel):
    """
    An image label that emits a signal when clicked with normalized coordinates.
    
    Signals:
        Clicked: Emitted when the label is clicked
        
    Properties:
        NormalizedX: Normalized X coordinate of the marker
        NormalizedY: Normalized Y coordinate of the marker
    """
    Clicked = Signal(QPoint)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the clickable image label.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.NormalizedX: Optional[float] = None
        self.NormalizedY: Optional[float] = None
        self.setMouseTracking(True)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """
        Handle mouse press events.
        
        Args:
            event: Mouse event
        """
        if event.button() == Qt.MouseButton.LeftButton:
            width, height = self.width(), self.height()
            if width > 0 and height > 0:
                self.NormalizedX = event.position().x() / width
                self.NormalizedY = event.position().y() / height
                self.Clicked.emit(event.position().toPoint())
                self.update()

    def SetMarkerNormalized(self, normalizedX: float, normalizedY: float) -> None:
        """
        Set the marker position using normalized coordinates.
        
        Args:
            normalizedX: Normalized X coordinate (0.0 to 1.0)
            normalizedY: Normalized Y coordinate (0.0 to 1.0)
        """
        self.NormalizedX = normalizedX
        self.NormalizedY = normalizedY
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        """
        Handle paint events to draw the marker.
        
        Args:
            event: Paint event
        """
        super().paintEvent(event)
        if self.NormalizedX is None or self.NormalizedY is None:
            return
            
        x = int(self.NormalizedX * self.width())
        y = int(self.NormalizedY * self.height())
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(Qt.GlobalColor.red, 2))
        
        size = 10
        painter.drawLine(x - size, y, x + size, y)
        painter.drawLine(x, y - size, x, y + size)


class HotkeyCaptureDialog(QDialog):
    """
    Dialog that captures a key combination when keys are pressed and released.
    
    Properties:
        CapturedVirtualKeyCodes: List of captured virtual key codes
    """
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the hotkey capture dialog.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("Capture Hotkey Combination")
        self.setFixedSize(250, 100)
        self.CapturedVirtualKeyCodes: List[int] = []
        self._currentVirtualKeyCodes: set[int] = set()
        
        layout = QVBoxLayout(self)
        self.StatusLabel = QLabel("Holding: 0 keys", alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.StatusLabel)
        self.setModal(True)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """
        Handle key press events.
        
        Args:
            event: Key event
        """
        virtualKeyCode = event.nativeVirtualKey()
        if virtualKeyCode > 0:
            self._currentVirtualKeyCodes.add(virtualKeyCode)
            self.StatusLabel.setText(f"Holding: {len(self._currentVirtualKeyCodes)} keys")

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        """
        Handle key release events.
        
        Args:
            event: Key event
        """
        # When keys are released, we finalize the list
        if self._currentVirtualKeyCodes:
            self.CapturedVirtualKeyCodes = list(self._currentVirtualKeyCodes)
            self.accept()


class CropperWidget(QWidget):
    """
    A PySide ROI selector that mimics the behavior of the Tkinter version.
    
    Properties:
        on_crop: Callback function when crop is complete
    """
    def __init__(
        self,
        imageData: np.ndarray[Any, Any],
        onCrop: Callable[[np.ndarray[Any, Any], float, float, float, float], None]
    ) -> None:
        """
        Initialize the cropper widget.
        
        Args:
            imageData: Image data to display
            onCrop: Callback function when crop is complete
        """
        super().__init__()
        self.onCrop = onCrop
        self.setMinimumSize(640, 480)  # Give it a starting minimum size
        
        # 1. Setup Layout
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 2. Setup Label
        self.imageLabel = QLabel()
        self.imageLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # This is critical: allows the label to shrink smaller than the image
        self.imageLabel.setMinimumSize(1, 1)
        
        # 3. Store the Original Pixmap
        self.originalPixmap = self._ndarrayToQPixmap(imageData)
        layout.addWidget(self.imageLabel)
        
        self.setLayout(layout)
        self.showMaximized()
        
        self.rubberBand = QRubberBand(QRubberBand.Shape.Rectangle, self.imageLabel)
        self.origin = QPoint()

    def resizeEvent(self, event: QResizeEvent) -> None:
        """
        Handle resize events to scale the image.
        
        Args:
            event: Resize event
        """
        if not self.originalPixmap.isNull():
            # Scale the original image to fit the current label size
            scaledPixmap = self.originalPixmap.scaled(
                self.imageLabel.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.imageLabel.setPixmap(scaledPixmap)
        super().resizeEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """
        Handle mouse press events to start selection.
        
        Args:
            event: Mouse event
        """
        if event.button() == Qt.MouseButton.LeftButton:
            self.origin = event.position().toPoint()
            self.rubberBand.setGeometry(QRect(self.origin, QSize()))
            self.rubberBand.show()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """
        Handle mouse move events to update selection.
        
        Args:
            event: Mouse event
        """
        if not self.origin.isNull():
            # Update selection rectangle dynamically
            self.rubberBand.setGeometry(QRect(self.origin, event.position().toPoint()).normalized())

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """
        Handle mouse release events to complete selection.
        
        Args:
            event: Mouse event
        """
        if event.button() == Qt.MouseButton.LeftButton:
            # 1. Get the geometry of the rubber band (Screen Space)
            selectionRect = self.rubberBand.geometry()
            
            # 2. Calculate the scaling ratio
            shownPixmapSize = self.imageLabel.pixmap().size()
            fullPixmapSize = self.originalPixmap.size()
            fullWidth = fullPixmapSize.width()
            fullHeight = fullPixmapSize.height()
            
            ratioX = fullWidth / shownPixmapSize.width()
            ratioY = fullHeight / shownPixmapSize.height()
            
            # 3. Calculate the actual crop area on the ORIGINAL image
            offsetX = (self.imageLabel.width() - shownPixmapSize.width()) / 2
            offsetY = (self.imageLabel.height() - shownPixmapSize.height()) / 2
            
            realX = int((selectionRect.x() - offsetX) * ratioX)
            realY = int((selectionRect.y() - offsetY) * ratioY)
            realW = int(selectionRect.width() * ratioX)
            realH = int(selectionRect.height() * ratioY)
            
            realRect = QRect(realX, realY, realW, realH)
            
            # --- Normalized Coordinates ---
            normX = float(realX) / float(fullWidth)
            normY = float(realY) / float(fullHeight)
            normW = float(realW) / float(fullWidth)
            normH = float(realH) / float(fullHeight)
            
            # 4. Crop from the high-res original
            croppedPixmap = self.originalPixmap.copy(realRect)
            cvImage = self._qpixmapToNdarray(croppedPixmap)
            
            # Passing normalized values to the callback
            self.onCrop(cvImage, normX, normY, normW, normH)
            self.close()

    def _qpixmapToNdarray(self, pixmap: QPixmap) -> np.ndarray[Any, Any]:
        """
        Convert QPixmap to NumPy array.
        
        Args:
            pixmap: QPixmap to convert
            
        Returns:
            NumPy array representation
        """
        # 1. Convert to a reliable format
        image = pixmap.toImage().convertToFormat(QImage.Format.Format_RGB888)
        width = image.width()
        height = image.height()
        bytesPerLine = image.bytesPerLine()  # This is the "772" in your case
        
        # 2. Get the memoryview
        ptr = image.bits()
        
        # 3. Create a 1D array first
        array = np.frombuffer(ptr, np.uint8)
        
        # 4. Reshape to (Height, BytesPerLine) to include padding
        # This matches the 169068 size perfectly
        array = array.reshape((height, bytesPerLine))
        
        # 5. Crop out the padding
        # We only want the first (width * 3) bytes of every row
        actualDataWidth = width * 3
        array = array[:, :actualDataWidth]
        
        # 6. Final reshape to (Height, Width, Channels)
        array = array.reshape((height, width, 3))
        
        # 7. Convert RGB to BGR and return a safe copy
        return cv2.cvtColor(array, cv2.COLOR_RGB2BGR).copy()

    def _ndarrayToQPixmap(self, cvImage: np.ndarray[Any, Any]) -> QPixmap:
        """
        Convert OpenCV BGR array to QPixmap.
        
        Args:
            cvImage: OpenCV BGR array
            
        Returns:
            QPixmap representation
        """
        height, width, _channel = cvImage.shape
        bytesPerLine = 3 * width
        
        # Convert BGR to RGB
        cvRgb = cv2.cvtColor(cvImage, cv2.COLOR_BGR2RGB)
        
        # Create QImage
        qImage = QImage(cvRgb.data, width, height, bytesPerLine, QImage.Format.Format_RGB888)
        
        # Important: QImage uses the underlying buffer of the ndarray.
        # We must return a copy as a Pixmap to avoid memory access issues.
        return QPixmap.fromImage(qImage)


class LeftPanelWidget(QWidget):    
    """
    Left panel widget containing event management controls.
    """
    def __init__(self, viewModel : DashboardViewModel) -> None:
        super().__init__()
        self.ViewModel = viewModel
        self._setupLeftPanel()
        self._wireUpBindings()

    def _setupLeftPanel(self) -> None:
        """Set up the left panel with event management controls."""

        layout = QVBoxLayout(self)
        buttonLayout = QHBoxLayout()
        
        self.addEventButton = QPushButton("+")
        self.removeEventButton = QPushButton("-")
        self.addEventButton.setFixedWidth(30)
        self.removeEventButton.setFixedWidth(30)
        
        self.saveEventButton = QPushButton("Save")
        self.loadEventButton = QPushButton("Load")
        self.saveEventButton.setFixedWidth(40)
        self.loadEventButton.setFixedWidth(40)
        
        buttonLayout.addWidget(self.addEventButton)
        buttonLayout.addWidget(self.removeEventButton)
        buttonLayout.addStretch()
        buttonLayout.addWidget(self.saveEventButton)
        buttonLayout.addWidget(self.loadEventButton)
        
        self.eventListWidget = QListWidget()
        self.eventListWidget.setFixedWidth(200)
        self.eventListWidget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        
        layout.addLayout(buttonLayout)
        layout.addWidget(self.eventListWidget)
        
        # Sentinel Control
        self.EventExecutionStateButton = QPushButton("Stop Sentinel")
        self.EventExecutionStateButton.setStyleSheet(BUTTON_STYLE_RUNNING)
        layout.addWidget(self.EventExecutionStateButton)
        
        # for Sentinel Control Hotkey capture dialog
        self.EventExecutionStateHotkeyEdit = QLineEdit()
        self.EventExecutionStateHotkeyEdit.setReadOnly(True)
        self.EventExecutionStateHotkeyButton = QPushButton("Capture Sentinel Hotkey")
        layout.addWidget(self.EventExecutionStateHotkeyEdit)
        layout.addWidget(self.EventExecutionStateHotkeyButton)

    def _wireUpBindings(self) -> None:
        """Wire up the UI components to the view model."""
        # to view model
        self.addEventButton.clicked.connect(self._onEventAddedClicked)
        self.removeEventButton.clicked.connect(self._onRemoveEventClicked)
        self.saveEventButton.clicked.connect(self._onSaveEventClicked)
        self.loadEventButton.clicked.connect(self._onLoadEventClicked)
        self.eventListWidget.currentItemChanged.connect(self._onEventListCurrentItemChanged)
        self.EventExecutionStateButton.clicked.connect(self._onEventExecutionStateClicked)
        self.EventExecutionStateHotkeyButton.clicked.connect(self._onEventExecutionStateHotkeyClicked)

        # Property Editing
        self.eventListWidget.itemChanged.connect(self._onEventItemChanged)

        # from view model
        self.ViewModel.EventItemAddedSignal.connect(self._onEventAddedSignal)
        self.ViewModel.EventItemRemovedSignal.connect(self._onRemoveEventSignal)
        self.ViewModel.EventItemSelectedSignal.connect(self._onEventItemSelectedSignal)
        self.ViewModel.EventItemChangedSignal.connect(self._onEventItemChangedSignal)
        self.ViewModel.EventExecutionStateChangedSignal.connect(self._onEventExecutionStateChangedSignal)
        self.ViewModel.EventExecutionStateHotkeyChangedSignal.connect(self._onEventExecutionStateHotkeyChangedSignal)

    def _onEventAddedClicked(self) -> None:
        self.ViewModel.AddEvent()

    def _onRemoveEventClicked(self) -> None:
        self.ViewModel.RemoveEvent()

    def _onSaveEventClicked(self) -> None:
        filePath, _ = QFileDialog.getSaveFileName(
            self,
            "Save Macro Configuration",
            "",
            "Data Files (*.dat);;Pickle Files (*.pkl);;All Files (*)"
        )
        if filePath:
            try:
                self.ViewModel.SaveState(filePath)
                QMessageBox.information(self, "Success", "Configuration saved successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save file: {e}")

    def _onLoadEventClicked(self) -> None:
        filePath, _ = QFileDialog.getOpenFileName(
            self,
            "Load Macro Configuration",
            "",
            "Data Files (*.dat);;Pickle Files (*.pkl);;All Files (*)"
        )
        if filePath:
            try:
                self.eventListWidget.clear()
                self.ViewModel.LoadState(filePath)
                QMessageBox.information(self, "Success", "Configuration loaded successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load file: {e}")

    def _onEventListCurrentItemChanged(self, current: QListWidgetItem, previous: QListWidgetItem) -> None:
        eventItem: EventItem = current.data(Qt.ItemDataRole.UserRole)
        self.ViewModel.SelectedEventItem = eventItem

    def _onEventExecutionStateClicked(self) -> None:
        self.ViewModel.ToggleSentinelFlow()

    def _onEventExecutionStateHotkeyClicked(self) -> None:
        dialog = HotkeyCaptureDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if self.ViewModel.TriggerThread is not None:
                self.ViewModel.TriggerThread.SetFlowHotkey(dialog.CapturedVirtualKeyCodes)
    
    # Property Editing
    def _onEventItemChanged(self, item: QListWidgetItem) -> None:
        eventItem: EventItem = item.data(Qt.ItemDataRole.UserRole)
        eventItem.IsEnabled = item.checkState() == Qt.CheckState.Checked
        eventItem.LoopCounter = 0 # TODO: need to move to view model

    # from view model
    def _onEventAddedSignal(self, eventItem: EventItem) -> None:
        item = QListWidgetItem(eventItem.Name)
        item.setData(Qt.ItemDataRole.UserRole, eventItem)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Checked if eventItem.IsEnabled else Qt.CheckState.Unchecked)
        self.eventListWidget.addItem(item)

    def _onRemoveEventSignal(self, index: int) -> None:
        self.eventListWidget.takeItem(index)

    def _onEventItemSelectedSignal(self, eventItem: EventItem) -> None:
        self.eventListWidget.currentItem().setText(eventItem.Name)

    def _onEventItemChangedSignal(self, eventItem: EventItem) -> None:
        for index in range(self.eventListWidget.count()):
            item = self.eventListWidget.item(index)
            storedEventItem: EventItem = item.data(Qt.ItemDataRole.UserRole)
            if storedEventItem == eventItem:
                item.setCheckState(Qt.CheckState.Checked if eventItem.IsEnabled else Qt.CheckState.Unchecked)
                break

    def _onEventExecutionStateChangedSignal(self, isRunning: bool) -> None:
        if isRunning:
            self.EventExecutionStateButton.setText("Stop Sentinel")
            self.EventExecutionStateButton.setStyleSheet(BUTTON_STYLE_RUNNING)
        else:
            self.EventExecutionStateButton.setText("Start Sentinel")
            self.EventExecutionStateButton.setStyleSheet(BUTTON_STYLE_STOPPED)

    def _onEventExecutionStateHotkeyChangedSignal(self, hotkeyList: List[int]) -> None:
        self.EventExecutionStateHotkeyEdit.setText(", ".join(map(KeyNameFromVk, hotkeyList)))


class DashboardView(QWidget):
    """
    Main UI view for the SentinelFlow dashboard.
    
    Properties:
        ViewModel: Reference to the dashboard view model
    """
    def __init__(self, viewModel: DashboardViewModel) -> None:
        """
        Initialize the dashboard view.
        
        Args:
            viewModel: View model for this view
        """
        super().__init__()
        self.ViewModel = viewModel
        self._initializeComponents()
        self._wireUpBindings()

    def _initializeComponents(self) -> None:
        """Initialize all UI components."""
        self.setWindowTitle("SentinelFlow Dashboard")
        self.resize(1000, 650)
        
        self.mainLayout = QHBoxLayout(self)
        self.mainLayout.setContentsMargins(0, 0, 0, 0)
        self.mainLayout.setSpacing(5)
        
        # Panels
        self.mainLayout.addWidget(LeftPanelWidget(self.ViewModel), 0)
        self.mainLayout.addLayout(self._setupCenterPanel(), 1)
        self.mainLayout.addWidget(self._setupRightPanel(), 0)

    def _setupCenterPanel(self) -> QVBoxLayout:
        """Set up the center panel with application management and live view."""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        mgmtGroupBox = QGroupBox("Target Application Management")
        mgmtGroupBox.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        
        groupMasterLayout = QVBoxLayout()
        groupMasterLayout.setContentsMargins(10, 15, 10, 10)
        
        # Row 1: Exe
        exeLayout = QHBoxLayout()
        self.exePathEdit = QLineEdit(r"C:\Users\HONG\Desktop\frozenthrone1.26\war3.exe -window")
        self.browseButton = QPushButton("Browse")
        self.launchButton = QPushButton("Launch")
        
        exeLayout.addWidget(QLabel("Path:"))
        exeLayout.addWidget(self.exePathEdit)
        exeLayout.addWidget(self.browseButton)
        exeLayout.addWidget(self.launchButton)
        groupMasterLayout.addLayout(exeLayout)
        
        # Row 2: Proc
        procLayout = QHBoxLayout()
        self.titleEdit = QLineEdit("Warcraft III")
        self.findWindowButton = QPushButton("Find Process")
        self.pidLabel = QLabel("Pid: -")
        
        procLayout.addWidget(QLabel("Title:"))
        procLayout.addWidget(self.titleEdit)
        procLayout.addWidget(self.findWindowButton)
        procLayout.addWidget(self.pidLabel)
        groupMasterLayout.addLayout(procLayout)
        
        # Row 3: Metrics
        resLayout = QHBoxLayout()
        self.resizeWidthEdit = QLineEdit("640")
        self.resizeHeightEdit = QLineEdit("480")
        self.resizeWindowButton = QPushButton("Resize Window")
        
        resLayout.addWidget(QLabel("W:"))
        resLayout.addWidget(self.resizeWidthEdit)
        resLayout.addWidget(QLabel("H:"))
        resLayout.addWidget(self.resizeHeightEdit)
        resLayout.addWidget(self.resizeWindowButton)
        groupMasterLayout.addLayout(resLayout)
        
        groupMasterLayout.addStretch(1)
        mgmtGroupBox.setLayout(groupMasterLayout)
        
        # Live View
        self.liveCaptureButton = QPushButton("Start Live Capture")
        self.liveCaptureButton.setCheckable(True)
        
        self.liveImageLabel = ClickableImageLabel()
        self.liveImageLabel.setScaledContents(True)
        self.liveImageLabel.setMinimumSize(640, 480)
        self.liveImageLabel.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.liveImageLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Interaction
        interactLayout = QHBoxLayout()
        self.keystrokeEdit = QLineEdit()
        self.sendKeystrokeButton = QPushButton("Send Key")
        self.mouseXEdit = QLineEdit()
        self.mouseYEdit = QLineEdit()
        self.sendClickButton = QPushButton("Send Click")
        
        interactLayout.addWidget(self.keystrokeEdit)
        interactLayout.addWidget(self.sendKeystrokeButton)
        interactLayout.addSpacing(10)
        interactLayout.addWidget(QLabel("X:"))
        interactLayout.addWidget(self.mouseXEdit)
        interactLayout.addWidget(QLabel("Y:"))
        interactLayout.addWidget(self.mouseYEdit)
        interactLayout.addWidget(self.sendClickButton)
        
        layout.addWidget(mgmtGroupBox)
        layout.addWidget(self.liveCaptureButton)
        layout.addWidget(self.liveImageLabel)
        layout.addLayout(interactLayout)
        
        return layout

    def _setupRightPanel(self) -> QWidget:
        """Set up the right panel with event configuration controls."""
        # Create a container to fix the width
        rightPanelContainer = QWidget()
        rightPanelContainer.setFixedWidth(350)
        
        layout = QVBoxLayout(rightPanelContainer)
        self.eventSettingsHeader = QLabel("<b>Event Settings</b>")
        
        # Event Properties
        self.eventNameEdit = QLineEdit()
        self.eventNameEdit.setEnabled(False)
        
        self.activationDropdown = QComboBox()
        self.activationDropdown.setEnabled(False)
        self.activationDropdown.addItems([activationType.name for activationType in ActivationType])
        
        # hotkey capture widget
        self.activationHotkeyWidget = QWidget()
        self.activationHotkeyLayout = QHBoxLayout()
        self.activationHotkeyLayout.addWidget(QLabel("Hotkey:"))
        self.activationHotkeyEdit = QLineEdit()
        self.activationHotkeyEdit.setReadOnly(True)
        self.activationHotkeyLayout.addWidget(self.activationHotkeyEdit)
        self.activationHotkeyButton = QPushButton("Capture")
        self.activationHotkeyLayout.addWidget(self.activationHotkeyButton)
        self.activationHotkeyButton.setEnabled(False)
        self.activationHotkeyWidget.setLayout(self.activationHotkeyLayout)
        self.activationHotkeyWidget.hide()
        
        # loop and interval widgets
        self.loopWidget = QWidget()
        self.loopWidgetLayout = QHBoxLayout()
        
        self.loopCountLayout = QVBoxLayout()
        self.loopCountLabel = QLabel("Count:")
        self.loopCountEdit = QLineEdit("1")
        self.loopCountLayout.addWidget(self.loopCountLabel)
        self.loopCountLayout.addWidget(self.loopCountEdit)
        
        self.loopIntervalLayout = QVBoxLayout()
        self.loopIntervalLabel = QLabel("Interval (ms):")
        self.loopIntervalEdit = QLineEdit("1000")
        self.loopIntervalLayout.addWidget(self.loopIntervalLabel)
        self.loopIntervalLayout.addWidget(self.loopIntervalEdit)
        
        self.loopWidgetLayout.addLayout(self.loopCountLayout)
        self.loopWidgetLayout.addLayout(self.loopIntervalLayout)
        self.loopWidget.setLayout(self.loopWidgetLayout)
        self.loopCountEdit.setEnabled(False)
        self.loopIntervalEdit.setEnabled(False)
        self.loopWidget.hide()
        
        # Roi widget
        self.roiWidget = QWidget()
        self.roiWidgetLayout = QHBoxLayout()
        self.roiWidgetLayoutInner = QVBoxLayout()
        
        self.roiXEditLayout = QHBoxLayout()
        self.roiYEditLayout = QHBoxLayout()
        self.roiWEditLayout = QHBoxLayout()
        self.roiHEditLayout = QHBoxLayout()
        
        self.roiXEdit = QLineEdit("0.0")
        self.roiYEdit = QLineEdit("0.0")
        self.roiWEdit = QLineEdit("1.0")
        self.roiHEdit = QLineEdit("1.0")
        
        self.roiXEditLayout.addWidget(QLabel("X:"))
        self.roiXEditLayout.addWidget(self.roiXEdit)
        self.roiYEditLayout.addWidget(QLabel("Y:"))
        self.roiYEditLayout.addWidget(self.roiYEdit)
        self.roiWEditLayout.addWidget(QLabel("W:"))
        self.roiWEditLayout.addWidget(self.roiWEdit)
        self.roiHEditLayout.addWidget(QLabel("H:"))
        self.roiHEditLayout.addWidget(self.roiHEdit)
        
        self.roiWidgetLayoutInner.addWidget(QLabel("Roi:"))
        self.roiWidgetLayoutInner.addLayout(self.roiXEditLayout)
        self.roiWidgetLayoutInner.addLayout(self.roiYEditLayout)
        self.roiWidgetLayoutInner.addLayout(self.roiWEditLayout)
        self.roiWidgetLayoutInner.addLayout(self.roiHEditLayout)
        
        self.roiButtonLayout = QVBoxLayout()
        self.roiButtonLayout.setContentsMargins(0, 0, 0, 0)
        self.roiButton = QPushButton("Select from Image")
        self.roiButton.setFixedSize(150, 150)
        self.roiButtonLayout.addWidget(self.roiButton)
        
        self.roiWidgetLayout.addLayout(self.roiWidgetLayoutInner)
        self.roiWidgetLayout.addLayout(self.roiButtonLayout)
        self.roiButton.setEnabled(False)
        self.roiWidget.setLayout(self.roiWidgetLayout)
        
        self.roiXEdit.setReadOnly(True)
        self.roiYEdit.setReadOnly(True)
        self.roiWEdit.setReadOnly(True)
        self.roiHEdit.setReadOnly(True)
        self.roiWidget.hide()
        
        # Threshold widget
        self.thresholdWidget = QWidget()
        self.thresholdWidgetLayout = QVBoxLayout()
        
        self.thresholdWidgetMatchScoreLayout = QHBoxLayout()
        self.thresholdMatchScoreLabel = QLabel("0.0")
        self.thresholdWidgetMatchScoreLayout.addWidget(QLabel("Match Score:"))
        self.thresholdWidgetMatchScoreLayout.addWidget(self.thresholdMatchScoreLabel)
        
        self.thresholdWidgetMatchScoreBtnLayout = QHBoxLayout()
        self.thresholdMatchScoreCopyButton = QPushButton("↓")
        self.thresholdMatchScoreCopyButton.setFixedWidth(30)
        self.thresholdWidgetMatchScoreBtnLayout.addWidget(self.thresholdMatchScoreCopyButton)
        
        self.thresholdWidgetThresholdLayout = QHBoxLayout()
        self.thresholdWidgetThresholdLayout.addWidget(QLabel("Threshold:"))
        self.thresholdEdit = QLineEdit("0.99")
        self.thresholdWidgetThresholdLayout.addWidget(self.thresholdEdit)
        
        self.thresholdWidgetLayout.addLayout(self.thresholdWidgetMatchScoreLayout)
        self.thresholdWidgetLayout.addLayout(self.thresholdWidgetMatchScoreBtnLayout)
        self.thresholdWidgetLayout.addLayout(self.thresholdWidgetThresholdLayout)
        self.thresholdWidget.setLayout(self.thresholdWidgetLayout)
        self.thresholdEdit.setEnabled(False)
        self.thresholdWidget.hide()
        
        # Trigger Type Specific Widgets
        self.triggerOnThresholdExceedLayout = QHBoxLayout()
        self.triggerOnThresholdExceedWidget = QWidget()
        self.triggerOnThresholdExceedCheckbox = QCheckBox("Trigger When Threshold Exceed")
        self.triggerOnThresholdExceedCheckbox.setEnabled(False)
        self.triggerOnThresholdExceedLayout.addWidget(self.triggerOnThresholdExceedCheckbox)
        self.triggerOnThresholdExceedWidget.setLayout(self.triggerOnThresholdExceedLayout)
        self.triggerOnThresholdExceedWidget.hide()

        # Retrigger Time Widget
        self.retriggerTimeWidget = QWidget()
        self.retriggerTimeLayout = QHBoxLayout()
        self.retriggerTimeLabel = QLabel("Retrigger Time (ms):")
        self.retriggerTimeEdit = QLineEdit("2000.0")
        self.retriggerTimeEdit.setEnabled(False)
        self.retriggerTimeLayout.addWidget(self.retriggerTimeLabel)
        self.retriggerTimeLayout.addWidget(self.retriggerTimeEdit)
        self.retriggerTimeWidget.setLayout(self.retriggerTimeLayout)
        self.retriggerTimeWidget.hide()
        
        # Action Sequence Properties
        self.actionNameLabel = QLabel("<b>Action Sequence</b>")
        
        # The actual list of MacroSteps
        self.macroStepListWidgetLayout = QHBoxLayout()
        self.macroStepListWidget = QListWidget()
        self.macroStepListWidget.setMinimumHeight(200)
        
        self.buttonMoveLayout = QVBoxLayout()
        self.buttonMoveUp = QPushButton("↑")
        self.buttonMoveDown = QPushButton("↓")
        self.buttonMoveUp.setFixedWidth(30)
        self.buttonMoveDown.setFixedWidth(30)
        self.buttonMoveUp.setEnabled(False)
        self.buttonMoveDown.setEnabled(False)
        
        self.macroStepListWidgetLayout.addWidget(self.macroStepListWidget)
        self.buttonMoveLayout.addWidget(self.buttonMoveUp)
        self.buttonMoveLayout.addWidget(self.buttonMoveDown)
        self.macroStepListWidgetLayout.addLayout(self.buttonMoveLayout)
        
        self.stepDropDown = QComboBox()
        self.stepDropDown.addItems([inputType.name for inputType in InputType])
        self.stepDropDown.setEnabled(False)
        
        # Buttons for Step Management
        stepButtonLayout = QHBoxLayout()
        self.addStepButton = QPushButton("Add Step")
        self.deleteStepButton = QPushButton("Remove Step")
        self.addStepButton.setEnabled(False)
        self.deleteStepButton.setEnabled(False)
        
        stepButtonLayout.addWidget(self.addStepButton)
        stepButtonLayout.addWidget(self.deleteStepButton)
        
        # Add to Layout
        layout.addWidget(self.eventSettingsHeader)
        layout.addWidget(QLabel("Event Name:"))
        layout.addWidget(self.eventNameEdit)
        layout.addWidget(QLabel("Trigger Type:"))
        layout.addWidget(self.activationDropdown)
        layout.addWidget(self.activationHotkeyWidget)
        layout.addWidget(self.loopWidget)
        layout.addWidget(self.roiWidget)
        layout.addWidget(self.thresholdWidget)
        layout.addWidget(self.triggerOnThresholdExceedWidget)
        layout.addWidget(self.retriggerTimeWidget)
        layout.addWidget(self.actionNameLabel)
        layout.addLayout(self.macroStepListWidgetLayout)
        layout.addWidget(self.stepDropDown)
        layout.addLayout(stepButtonLayout)
        layout.addStretch()
        
        return rightPanelContainer
    
    def _wireUpBindings(self) -> None:
        """Connect UI signals to ViewModel methods and ViewModel signals to UI updates."""
        # --- View to ViewModel ---
        
        self.findWindowButton.clicked.connect(lambda: self.ViewModel.FindWindow(self.titleEdit.text().strip()))
        self.browseButton.clicked.connect(self._onBrowseExecutable)
        self.launchButton.clicked.connect(self._onLaunchExecutable)
        self.resizeWindowButton.clicked.connect(self._onResizeRequested)
        
        self.liveCaptureButton.toggled.connect(self._onToggleCapture)
        
        self.buttonMoveUp.clicked.connect(lambda: self._moveStep(-1))
        self.buttonMoveDown.clicked.connect(lambda: self._moveStep(1))
        
        self.addStepButton.clicked.connect(self._onAddStepClicked)
        self.deleteStepButton.clicked.connect(self._onRemoveStepClicked)
        
        self.activationHotkeyButton.clicked.connect(self._onCaptureHotkey)
        self.roiButton.clicked.connect(self._onSelectRoi)
        
        # Interaction
        self.liveImageLabel.Clicked.connect(self._onImageClicked)
        self.sendClickButton.clicked.connect(self._onSendMouseClick)
        self.sendKeystrokeButton.clicked.connect(self._onSendKeystroke)
        
        self.mouseXEdit.textChanged.connect(self._onManualCoordsChanged)
        self.mouseYEdit.textChanged.connect(self._onManualCoordsChanged)
        
        self.thresholdMatchScoreCopyButton.clicked.connect(self._onCopyMatchScoreToThreshold)
        
        # Property Editing
        self.eventNameEdit.editingFinished.connect(self._onCommitEventName)
        self.activationDropdown.currentIndexChanged.connect(self._onCommitActivationType)
        
        self.loopCountEdit.editingFinished.connect(self._onCommitLoopCount)
        self.loopIntervalEdit.editingFinished.connect(self._onCommitLoopInterval)
        
        self.thresholdEdit.editingFinished.connect(self._onCommitThreshold)
        self.triggerOnThresholdExceedCheckbox.stateChanged.connect(self._onCommitTriggerOnThresholdExceed)
        self.retriggerTimeEdit.editingFinished.connect(self._onCommitRetriggerTime)
        
        # --- ViewModel to View ---
        self.ViewModel.WindowHandleUpdated.connect(self._updateUiWindowHandleInfo)
        self.ViewModel.CaptureImageReady.connect(self._updateUiImage)
        self.ViewModel.MatchScoreUpdated.connect(self._updateUiEventMatchScore)
        self.ViewModel.EventItemSelectedSignal.connect(self._onEventItemSelectedSignal)

    def _onBrowseExecutable(self) -> None:
        """Handle browse executable button click."""
        path, _ = QFileDialog.getOpenFileName(self, "Select EXE", "", "Executables (*.exe)")
        if path:
            self.exePathEdit.setText(path)

    def _onLaunchExecutable(self) -> None:
        """Handle launch executable button click."""
        pid = self.ViewModel.LaunchApplication(self.exePathEdit.text().strip())
        if pid:
            QMessageBox.information(self, "Success", f"Launched PID: {pid}")

    def _onResizeRequested(self) -> None:
        """Handle resize window button click."""
        try:
            width, height = int(self.resizeWidthEdit.text()), int(self.resizeHeightEdit.text())
            self.ViewModel.ResizeTargetWindow(width, height)
        except ValueError:
            QMessageBox.warning(self, "Error", "Invalid dimensions.")

    def _onToggleCapture(self, checked: bool) -> None:
        """
        Handle live capture toggle.
        
        Args:
            checked: Whether capture is enabled
        """
        if checked and not self.ViewModel.CurrentWindowHandle:
            self.liveCaptureButton.setChecked(False)
            QMessageBox.warning(self, "Error", "Please find a window first.")
            return
            
        self.ViewModel.ToggleCapture(checked)

    def _onAddStepClicked(self) -> None:
        """Handle add step button click."""
        eventItem = self.ViewModel.SelectedEventItem
        if not eventItem:
            return
        
        if eventItem.AssignedAction:
            stepTypeName = self.stepDropDown.currentText()
            if stepTypeName in InputType.__members__:
                stepType = InputType[stepTypeName]
                # Create a default step based on type
                newStep = None
                if stepType == InputType.Mouse:
                    try:
                        normalizedX, normalizedY = float(self.mouseXEdit.text()), float(self.mouseYEdit.text())
                        newStep = MacroStep(InputType.Mouse, (normalizedX, normalizedY), f"Click at ({normalizedX:.7f}, {normalizedY:.7f})")
                    except ValueError:
                        QMessageBox.warning(self, "Error", "Invalid coordinates.")
                        return
                elif stepType == InputType.Keyboard:
                    dialog = HotkeyCaptureDialog(self)
                    if dialog.exec() == QDialog.DialogCode.Accepted:
                        # We take the first key from the captured list
                        if dialog.CapturedVirtualKeyCodes:
                            virtualKeyCode = dialog.CapturedVirtualKeyCodes[0]
                            newStep = MacroStep(InputType.Keyboard, virtualKeyCode, f"Press \"{KeyNameFromVk(virtualKeyCode)}\"")
                        else:
                            return
                    else:
                        return
                elif stepType == InputType.Delay:
                    milliseconds, ok = QInputDialog.getInt(self, "Add Delay", "Milliseconds (ms):", 100, 1, 60000, 10)
                    if ok:
                        newStep = MacroStep(InputType.Delay, milliseconds, f"Wait {milliseconds}ms")
                    else:
                        return
                
                if newStep is not None:
                    eventItem.AssignedAction.AddStep(newStep)
                    self._refreshMacroStepList(eventItem.AssignedAction)

    def _onRemoveStepClicked(self) -> None:
        """Handle remove step button click."""
        currentRow = self.macroStepListWidget.currentRow()
        eventItem = self.ViewModel.SelectedEventItem
        if eventItem and currentRow >= 0:
            if eventItem.AssignedAction:
                eventItem.AssignedAction.RemoveStep(currentRow)
                self._refreshMacroStepList(eventItem.AssignedAction)

    def _onCaptureHotkey(self) -> None:
        """Handle capture hotkey button click."""
        eventItem = self.ViewModel.SelectedEventItem
        if not eventItem:
            return
            
        dialog = HotkeyCaptureDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            eventItem.ActivationVirtualKeyCodes = dialog.CapturedVirtualKeyCodes
            # Show the raw VKs on the button for debugging/clarity
            self.activationHotkeyEdit.setText(", ".join(map(KeyNameFromVk, eventItem.ActivationVirtualKeyCodes)))

    def _onSelectRoi(self) -> None:
        """Handle select ROI button click."""
        if self.ViewModel.LastLiveImage is None:
            # Handle the case where there is no image
            QMessageBox.warning(self, "Error", "Please start the capture before selecting an ROI.")
            return
            
        self.cropper = CropperWidget(self.ViewModel.LastLiveImage, self._handleNewCrop)
        self.cropper.show()

    def _handleNewCrop(
        self,
        cvImage: np.ndarray[Any, Any],
        normalizedX: float,
        normalizedY: float,
        normalizedWidth: float,
        normalizedHeight: float
    ) -> None:
        """
        Handle a new crop selection.
        
        Args:
            cvImage: Cropped image data
            normalizedX: Normalized X coordinate
            normalizedY: Normalized Y coordinate
            normalizedWidth: Normalized width
            normalizedHeight: Normalized height
        """
        # set model
        eventItem = self.ViewModel.SelectedEventItem
        if eventItem:
            eventItem.TemplateImage = cvImage
            eventItem.Roi = RectangleRegion(normalizedX, normalizedY, normalizedWidth, normalizedHeight)
            
            # set view
            self._setButtonWithImage(self.roiButton, cvImage)
            self.roiXEdit.setText(f"{normalizedX:.4f}")
            self.roiYEdit.setText(f"{normalizedY:.4f}")
            self.roiWEdit.setText(f"{normalizedWidth:.4f}")
            self.roiHEdit.setText(f"{normalizedHeight:.4f}")

    def _setButtonWithImage(self, button: QPushButton, cvImage: np.ndarray[Any, Any]) -> None:
        """
        Set a button's icon to display an image.
        
        Args:
            button: Button to update
            cvImage: Image data to display
        """
        height, width, _channel = cvImage.shape
        bytesPerLine = 3 * width
        cvRgb = cv2.cvtColor(cvImage, cv2.COLOR_BGR2RGB)
        qImage = QImage(cvRgb.data, width, height, bytesPerLine, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qImage)
        icon = QIcon(pixmap)
        button.setIcon(icon)
        button.setIconSize(button.size())
        button.setText("")

    def _onCaptureSentinelHotkey(self) -> None:
        """Handle capture sentinel hotkey button click."""
        dialog = HotkeyCaptureDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if self.ViewModel.TriggerThread is not None:
                self.ViewModel.TriggerThread.SetFlowHotkey(dialog.CapturedVirtualKeyCodes)

    def _onImageClicked(self, position: QPoint) -> None:
        """
        Handle image click events.
        
        Args:
            position: Click position
        """
        normalizedX = float(position.x()) / self.liveImageLabel.width()
        normalizedY = float(position.y()) / self.liveImageLabel.height()
        self.mouseXEdit.setText(f"{normalizedX:.7f}")
        self.mouseYEdit.setText(f"{normalizedY:.7f}")

    def _onManualCoordsChanged(self) -> None:
        """Handle manual coordinate changes."""
        try:
            normalizedX = float(self.mouseXEdit.text()) if self.mouseXEdit.text() else 0.0
            normalizedY = float(self.mouseYEdit.text()) if self.mouseYEdit.text() else 0.0
            self.liveImageLabel.SetMarkerNormalized(normalizedX, normalizedY)
        except ValueError:
            pass

    def _onCopyMatchScoreToThreshold(self) -> None:
        """Handle copy match score to threshold button click."""
        scoreText = self.thresholdMatchScoreLabel.text()
        self.thresholdEdit.setText(scoreText)

    def _onSendMouseClick(self) -> None:
        """Handle send mouse click button click."""
        if self.ViewModel.CurrentWindowHandle:
            try:
                normalizedX, normalizedY = float(self.mouseXEdit.text()), float(self.mouseYEdit.text())
                SendMouseClickToWindow(self.ViewModel.CurrentWindowHandle, normalizedX, normalizedY)
            except ValueError:
                QMessageBox.warning(self, "Error", "Invalid coordinates.")

    def _onSendKeystroke(self) -> None:
        """Handle send keystroke button click."""
        keyName = self.keystrokeEdit.text().strip()
        if keyName and self.ViewModel.CurrentWindowHandle:
            virtualKeyCode = VkFromKeyName(keyName)
            if virtualKeyCode:
                SendKeystrokeToWindow(self.ViewModel.CurrentWindowHandle, virtualKeyCode)
            else:
                QMessageBox.warning(self, "Error", f"Unknown key: {keyName}")

    def _onEventItemSelectedSignal(self, eventItem: EventItem) -> None:
        if not eventItem:
            self.eventNameEdit.clear()
            self.macroStepListWidget.clear()
            self.eventNameEdit.setEnabled(False)
            self.activationDropdown.setEnabled(False)
            self.activationHotkeyButton.setEnabled(False)
            self.loopCountEdit.setEnabled(False)
            self.loopIntervalEdit.setEnabled(False)
            self.stepDropDown.setEnabled(False)
            self.addStepButton.setEnabled(False)
            self.deleteStepButton.setEnabled(False)
            self.buttonMoveUp.setEnabled(False)
            self.buttonMoveDown.setEnabled(False)
            self.thresholdEdit.setEnabled(False)
            self.triggerOnThresholdExceedCheckbox.setEnabled(False)
            self.retriggerTimeEdit.setEnabled(False)
            self.roiButton.setEnabled(False)
            return
            

        self.eventNameEdit.setText(eventItem.Name)
        self.eventNameEdit.setEnabled(True)
        
        activation = eventItem.SelectedActivationType
        typeName = activation.name if hasattr(activation, 'name') else str(activation)
        index = self.activationDropdown.findText(typeName)
        if index >= 0:
            self.activationDropdown.setCurrentIndex(index)
            
        self.activationDropdown.setEnabled(True)
        
        self.activationHotkeyEdit.setText(", ".join(map(KeyNameFromVk, eventItem.ActivationVirtualKeyCodes)))
        self.activationHotkeyButton.setEnabled(True)
        
        self.loopCountEdit.setText(str(eventItem.LoopCount))
        self.loopIntervalEdit.setText(str(eventItem.IntervalMilliseconds))
        self.loopCountEdit.setEnabled(True)
        self.loopIntervalEdit.setEnabled(True)
        
        self.roiXEdit.setText(f"{eventItem.Roi.XNormalized:.4f}")
        self.roiYEdit.setText(f"{eventItem.Roi.YNormalized:.4f}")
        self.roiWEdit.setText(f"{eventItem.Roi.WidthNormalized:.4f}")
        self.roiHEdit.setText(f"{eventItem.Roi.HeightNormalized:.4f}")
        
        if eventItem.TemplateImage is not None:
            self._setButtonWithImage(self.roiButton, eventItem.TemplateImage)
        else:
            self.roiButton.setIcon(QIcon())  # Optionally clear the icon if no image
            self.roiButton.setText("Select from Image")
            
        self.roiButton.setEnabled(True)
        
        self.thresholdEdit.setText(f"{eventItem.Threshold}")
        self.thresholdEdit.setEnabled(True)
        
        self.triggerOnThresholdExceedCheckbox.setChecked(eventItem.TriggerOnThresholdExceed)
        self.triggerOnThresholdExceedCheckbox.setEnabled(True)

        self.retriggerTimeEdit.setText(str(eventItem.RetriggerTimeMilliseconds))
        self.retriggerTimeEdit.setEnabled(True)
        
        self._refreshMacroStepList(eventItem.AssignedAction)
        
        self.stepDropDown.setEnabled(True)
        self.addStepButton.setEnabled(True)
        self.deleteStepButton.setEnabled(True)
        self.buttonMoveUp.setEnabled(True)
        self.buttonMoveDown.setEnabled(True)

    def _refreshMacroStepList(self, actionObj: ActionItem) -> None:
        """
        Refresh the macro step list UI.
        
        Args:
            actionObj: Action containing the steps
        """
        self.macroStepListWidget.clear()
        for step in actionObj.MacroSteps:
            # Check if it's a dict (raw data) or an object
            description = ""
            if isinstance(step, dict):
                description = cast(Dict[str, Any], step).get("Description", "Unknown Step")
            else:
                description = step.Description
                
            item = QListWidgetItem(description)
            item.setData(Qt.ItemDataRole.UserRole, step)  # Store the step data/object
            self.macroStepListWidget.addItem(item)

    def _onCommitEventName(self) -> None:
        """Commit event name changes."""
        eventItem = self.ViewModel.SelectedEventItem
        if not eventItem:
            return
        eventItem.Name = self.eventNameEdit.text().strip()
        self.ViewModel.SelectedEventItem = eventItem  # Trigger update

    def _onCommitActivationType(self, index: int) -> None:
        """
        Commit activation type changes.
        
        Args:
            index: Selected index
        """
        eventItem = self.ViewModel.SelectedEventItem
        if not eventItem:
            return
        typeName = self.activationDropdown.currentText()
        # Update via the new property name
        eventItem.SelectedActivationType = ActivationType[typeName]
        
        if eventItem.SelectedActivationType == ActivationType.Hotkey:
            self.activationHotkeyWidget.show()
        else:
            self.activationHotkeyWidget.hide()
            
        if eventItem.SelectedActivationType == ActivationType.Loop:
            self.loopWidget.show()
        else:
            self.loopWidget.hide()
            
        if eventItem.SelectedActivationType == ActivationType.ImageMatchRoi:
            self.roiWidget.show()
            self.thresholdWidget.show()
            self.triggerOnThresholdExceedWidget.show()
            self.retriggerTimeWidget.show()
        elif eventItem.SelectedActivationType == ActivationType.ProgessBar:
            self.roiWidget.show()
            self.thresholdWidget.show()
            self.triggerOnThresholdExceedWidget.show()
            self.retriggerTimeWidget.show()
        else:
            self.roiWidget.hide()
            self.thresholdWidget.hide()
            self.triggerOnThresholdExceedWidget.hide()
            self.retriggerTimeWidget.hide()

    def _onCommitLoopCount(self) -> None:
        """Commit loop count changes."""
        eventItem = self.ViewModel.SelectedEventItem
        if not eventItem:
            return
        try:
            count = int(self.loopCountEdit.text())
            eventItem.LoopCount = count
        except ValueError:
            QMessageBox.warning(self, "Error", "Invalid loop count.")

    def _onCommitLoopInterval(self) -> None:
        """Commit loop interval changes."""
        eventItem = self.ViewModel.SelectedEventItem
        if not eventItem:
            return
        try:
            interval = int(self.loopIntervalEdit.text())
            eventItem.IntervalMilliseconds = interval
        except ValueError:
            QMessageBox.warning(self, "Error", "Invalid interval.")

    def _onCommitThreshold(self) -> None:
        """Commit threshold changes."""
        eventItem = self.ViewModel.SelectedEventItem
        if not eventItem:
            return
        try:
            threshold = float(self.thresholdEdit.text())
            eventItem.Threshold = threshold
        except ValueError:
            QMessageBox.warning(self, "Error", "Invalid threshold.")

    def _onCommitTriggerOnThresholdExceed(self, checked: bool) -> None:
        """
        Commit trigger when match changes.
        
        Args:
            checked: Check state
        """
        eventItem = self.ViewModel.SelectedEventItem
        if not eventItem:
            return
        eventItem.TriggerOnThresholdExceed = checked

    def _onCommitRetriggerTime(self) -> None:
        """Commit retrigger time changes."""
        eventItem = self.ViewModel.SelectedEventItem
        if not eventItem:
            return
        try:
            retriggerTime = float(self.retriggerTimeEdit.text())
            eventItem.RetriggerTimeMilliseconds = retriggerTime
        except ValueError:
            QMessageBox.warning(self, "Error", "Invalid retrigger time.")

    def _moveStep(self, direction: int) -> None:
        """
        Move a step up or down in the list.
        
        Args:
            direction: -1 for Up, 1 for Down
        """
        # 1. Get current selection
        currentRow = self.macroStepListWidget.currentRow()
        if currentRow == -1:
            return
            
        # 2. Calculate target row and check boundaries
        targetRow = currentRow + direction
        if targetRow < 0 or targetRow >= self.macroStepListWidget.count():
            return
            
        # 3. Get the Action object from the selected Event
        eventItem = self.ViewModel.SelectedEventItem
        if not eventItem:
            return
            
        steps = eventItem.AssignedAction.MacroSteps
        
        # 4. Swap in the Python List (The Data Model)
        steps[currentRow], steps[targetRow] = steps[targetRow], steps[currentRow]
        
        # 5. Swap in the UI (The View)
        # We take the item out and re-insert it at the new position
        item = self.macroStepListWidget.takeItem(currentRow)
        self.macroStepListWidget.insertItem(targetRow, item)
        
        # 6. Keep the moved item selected so the user can click multiple times
        self.macroStepListWidget.setCurrentRow(targetRow)


    def _updateUiWindowHandleInfo(self, windowHandle: Optional[int]) -> None:
        """
        Update UI with window handle information.
        
        Args:
            windowHandle: Window handle
        """
        if windowHandle:
            self.pidLabel.setText(f"PID: {FindPidByHwnd(windowHandle)}")
        else:
            self.pidLabel.setText("PID: -")
            QMessageBox.warning(self, "Error", "Window not found.")

    def _updateUiImage(self, image: Optional[np.ndarray[Any, Any]]) -> None:
        """
        Update UI with a new image.
        
        Args:
            image: Image data to display
        """
        if image is not None:
            height, width, channels = image.shape
            qImage = QImage(image.data, width, height, channels * width, QImage.Format.Format_BGR888)
            pixmap = QPixmap.fromImage(qImage).scaled(
                self.liveImageLabel.width(), self.liveImageLabel.height(),
                Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            self.liveImageLabel.setPixmap(pixmap)
        else:
            self.liveImageLabel.clear()

    def _updateUiEventMatchScore(self, score: float) -> None:
        """
        Update UI with event match score.
        
        Args:
            eventTuple: Tuple containing (index, score)
        """
        self.thresholdMatchScoreLabel.setText(f"{score}")

    def closeEvent(self, event: QCloseEvent) -> None:
        """
        Handle window close event.
        
        Args:
            event: Close event
        """
        self.ViewModel.StopCapture()
        super().closeEvent(event)




# =============================================================================
# MAIN ENTRY POINT
# =============================================================================
if __name__ == "__main__":
    application = QApplication(sys.argv)
    
    # MVVM Initialization
    viewModel = DashboardViewModel()
    view = DashboardView(viewModel)
    view.show()
    
    sys.exit(application.exec())