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
    cast, List, Optional, Tuple, Any, Callable, Dict, Final
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
    QSizePolicy, QListWidgetItem, QComboBox, QGroupBox, QFrame,
    QDialog, QInputDialog, QRubberBand, QCheckBox
)
from PySide6.QtGui import (
    QPainter, QPen, QImage, QPixmap, QIcon, QKeyEvent,
    QMouseEvent, QPaintEvent, QResizeEvent, QCloseEvent
)

# Local imports
from Src.Helper import (
    sendKeystrokeToWindow, sendMouseClickToWindow, captureWindowByHwnd,
    findHwndByTitle, launchHwndByExecutable, ResizeWindow, IsHotkeyActive,
    KeyNameFromVk, vkFromKeyName, cropImage, matchTemplate,
    estimateProgressBarPercentage, findPidByHwnd
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
    def __init__(self, xN: float = 0.0, yN: float = 0.0, wN: float = 1.0, hN: float = 1.0) -> None:
        """
        Initialize a normalized rectangle region.
        
        Args:
            xN: Normalized X coordinate (0.0 to 1.0)
            yN: Normalized Y coordinate (0.0 to 1.0)
            wN: Normalized width (0.0 to 1.0)
            hN: Normalized height (0.0 to 1.0)
        """
        self._xN: float = xN
        self._yN: float = yN
        self._wN: float = wN
        self._hN: float = hN

    @property
    def XN(self) -> float:
        """Get the normalized X coordinate."""
        return self._xN

    @XN.setter
    def XN(self, value: float) -> None:
        """Set the normalized X coordinate."""
        self._xN = value

    @property
    def YN(self) -> float:
        """Get the normalized Y coordinate."""
        return self._yN

    @YN.setter
    def YN(self, value: float) -> None:
        """Set the normalized Y coordinate."""
        self._yN = value

    @property
    def WN(self) -> float:
        """Get the normalized width."""
        return self._wN

    @WN.setter
    def WN(self, value: float) -> None:
        """Set the normalized width."""
        self._wN = value

    @property
    def HN(self) -> float:
        """Get the normalized height."""
        return self._hN

    @HN.setter
    def HN(self, value: float) -> None:
        """Set the normalized height."""
        self._hN = value


class MacroStep:
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
        if self._inputType == self.InputType.Keyboard:
            self._sendKeystroke(windowHandle, self._value)
        elif self._inputType == self.InputType.Mouse:
            # self._value is expected to be a tuple (xN, yN)
            self._sendMouseClick(windowHandle, self._value[0], self._value[1])
        elif self._inputType == self.InputType.Delay:
            # self._value is milliseconds
            time.sleep(self._value / 1000.0)

    def _sendKeystroke(self, hwnd: int, vk: int) -> None:
        """
        Send a keyboard keystroke to the specified window.
        
        Args:
            hwnd: Window handle
            vk: Virtual key code
        """
        sendKeystrokeToWindow(hwnd, vk)

    def _sendMouseClick(self, hwnd: int, xN: float, yN: float) -> None:
        """
        Send a mouse click to normalized coordinates in the specified window.
        
        Args:
            hwnd: Window handle
            xN: Normalized X coordinate (0.0 to 1.0)
            yN: Normalized Y coordinate (0.0 to 1.0)
        """
        sendMouseClickToWindow(hwnd, xN, yN)


class ActionItem:
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
    def __init__(
        self,
        name: str,
        action: ActionItem,
        enabled: bool = False,
        activationType: ActivationType = ActivationType.NotSet,
        loopCount: int = 0,
        intervalMs: int = 1000,
        roi: RectangleRegion = RectangleRegion(0.0, 0.0, 1.0, 1.0),
        threshold: float = 0.99
    ) -> None:
        """
        Initialize an event item.
        
        Args:
            name: Name of the event
            action: Action to execute when triggered
            enabled: Whether the event is active
            activationType: Type of activation mechanism
            loopCount: Number of times to loop (0 = infinite, -1 = disabled)
            intervalMs: Interval between loop executions in milliseconds
            roi: Region of interest for image matching
            threshold: Threshold for image matching or progress bar
        """
        self._name: str = name
        self._enabled: bool = enabled
        self._selectedActivationType: ActivationType = activationType
        self._activationVkList: List[int] = []
        self.__isCurrentlyHeld: bool = False
        self._loopCount: int = loopCount
        self.__loopCounter: int = 0
        self._intervalMs: int = intervalMs
        self.__timeOfLastTriggerMs: float = 0.0
        self._roi: RectangleRegion = roi
        self._threshold: float = threshold
        self._triggerWhenMatch: bool = True
        self.__matchScore: float = 0.0
        self.__templateImage: Optional[np.ndarray[Any, Any]] = None
        self.__percentFilled: float = 0.0
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
    def Enabled(self) -> bool:
        """Get whether this event is enabled."""
        return self._enabled

    @Enabled.setter
    def Enabled(self, value: bool) -> None:
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
    def ActivationVkList(self) -> List[int]:
        """Get the list of virtual key codes for hotkey activation."""
        return self._activationVkList

    @ActivationVkList.setter
    def ActivationVkList(self, value: List[int]) -> None:
        """Set the list of virtual key codes for hotkey activation."""
        self._activationVkList = value

    @property
    def IsCurrentlyHeld(self) -> bool:
        """Get the current state of hotkey activation."""
        return self.__isCurrentlyHeld

    @IsCurrentlyHeld.setter
    def IsCurrentlyHeld(self, value: bool) -> None:
        """Set the current state of hotkey activation."""
        self.__isCurrentlyHeld = value

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
        return self.__loopCounter

    @LoopCounter.setter
    def LoopCounter(self, value: int) -> None:
        """Set the current loop iteration count."""
        self.__loopCounter = value

    @property
    def IntervalMs(self) -> int:
        """Get the interval between loop executions in milliseconds."""
        return self._intervalMs

    @IntervalMs.setter
    def IntervalMs(self, value: int) -> None:
        """Set the interval between loop executions in milliseconds."""
        self._intervalMs = value

    @property
    def TimeOfLastTriggerMs(self) -> float:
        """Get the timestamp of last trigger in milliseconds."""
        return self.__timeOfLastTriggerMs

    @TimeOfLastTriggerMs.setter
    def TimeOfLastTriggerMs(self, value: float) -> None:
        """Set the timestamp of last trigger in milliseconds."""
        self.__timeOfLastTriggerMs = value

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
        return self.__templateImage

    @TemplateImage.setter
    def TemplateImage(self, value: Optional[np.ndarray[Any, Any]]) -> None:
        """Set the template image for image matching."""
        self.__templateImage = value

    @property
    def Threshold(self) -> float:
        """Get the threshold for image matching or progress bar."""
        return self._threshold

    @Threshold.setter
    def Threshold(self, value: float) -> None:
        """Set the threshold for image matching or progress bar."""
        self._threshold = value

    @property
    def TriggerWhenMatch(self) -> bool:
        """Get whether to trigger when match is found or not found."""
        return self._triggerWhenMatch

    @TriggerWhenMatch.setter
    def TriggerWhenMatch(self, value: bool) -> None:
        """Set whether to trigger when match is found or not found."""
        self._triggerWhenMatch = value

    @property
    def MatchScore(self) -> float:
        """Get the last match score from image matching."""
        return self.__matchScore

    @MatchScore.setter
    def MatchScore(self, value: float) -> None:
        """Set the last match score from image matching."""
        self.__matchScore = value

    @property
    def PercentFilled(self) -> float:
        """Get the last percentage filled from progress bar detection."""
        return self.__percentFilled

    @PercentFilled.setter
    def PercentFilled(self, value: float) -> None:
        """Set the last percentage filled from progress bar detection."""
        self.__percentFilled = value

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
    EventTriggered = Signal(EventItem)
    EventDisabled = Signal(EventItem)
    FlowChanged = Signal(bool)
    FlowHotkeyChanged = Signal(list)
    MatchScoreUpdated = Signal(tuple)  # (index, score)

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
        self._image_mutex: QMutex = QMutex()
        self._current_img: Optional[np.ndarray[Any, Any]] = None
        
        # Flow control
        self._flow: bool = True
        self._flowHotkeyVkList: List[int] = []
        self._flowHotkeyIsCurrentlyHeld: bool = False

    def SetImage(self, img: Optional[np.ndarray[Any, Any]]) -> None:
        """
        Set the current image for processing.
        
        Args:
            img: Image data to process
        """
        with QMutexLocker(self._image_mutex):
            self._current_img = img

    def SetFlow(self, flow: bool) -> None:
        """
        Set the flow state directly.
        
        Args:
            flow: New flow state
        """
        self._flow = flow
        self.FlowChanged.emit(self._flow)

    def ToggleFlow(self) -> None:
        """Toggle the flow state."""
        self.SetFlow(not self._flow)

    def SetFlowHotkey(self, vkList: List[int]) -> None:
        """
        Set the hotkey to toggle flow state.
        
        Args:
            vkList: List of virtual key codes
        """
        self._flowHotkeyVkList = vkList
        print(f"Flow hotkey set to: {vkList}")
        self.FlowHotkeyChanged.emit(vkList)

    def GetFlowHotkey(self) -> List[int]:
        """Get the current flow hotkey virtual key codes."""
        return self._flowHotkeyVkList

    def run(self) -> None:
        """Main thread execution loop."""
        while self._isRunning:
            # Check flow hotkey
            isDownNow = IsHotkeyActive(self._flowHotkeyVkList)
            if self._flowHotkeyIsCurrentlyHeld and not isDownNow:
                self.ToggleFlow()
            self._flowHotkeyIsCurrentlyHeld = isDownNow
            
            if not self._flow:
                time.sleep(self._pollIntervalMs / 1000.0)
                continue
            
            # Copy image for processing
            local_img: Optional[np.ndarray[Any, Any]] = None
            with QMutexLocker(self._image_mutex):
                local_img = self._current_img
                self._current_img = None
            
            # Process each event
            for index, event in enumerate(self._viewModel.EventItems):
                if not event.Enabled:
                    continue
                
                if event.SelectedActivationType == ActivationType.Hotkey:
                    if len(event.ActivationVkList) == 0:
                        continue
                    
                    isDownNow = IsHotkeyActive(event.ActivationVkList)
                    if event.IsCurrentlyHeld and not isDownNow:
                        self.EventTriggered.emit(event)
                    event.IsCurrentlyHeld = isDownNow
                
                elif event.SelectedActivationType == ActivationType.Loop:
                    if event.LoopCount < 0:
                        continue
                    elif event.LoopCount > 0:
                        if event.LoopCounter >= event.LoopCount:
                            event.Enabled = False
                            self.EventDisabled.emit(event)
                    
                    # Handle loop timing
                    if time.time() * 1000 - event.TimeOfLastTriggerMs < event.IntervalMs:
                        continue
                    
                    event.LoopCounter += 1
                    event.TimeOfLastTriggerMs = time.time() * 1000
                    self.EventTriggered.emit(event)
                
                elif event.SelectedActivationType == ActivationType.ImageMatchRoi:
                    if local_img is None or event.TemplateImage is None:
                        continue
                    
                    local_img_roi = cropImage(local_img, (event.Roi.XN, event.Roi.YN, event.Roi.WN, event.Roi.HN))
                    event.MatchScore = matchTemplate(local_img_roi, event.TemplateImage)
                    
                    if event.TriggerWhenMatch:
                        isMatchNow = event.MatchScore >= event.Threshold
                    else:
                        isMatchNow = event.MatchScore < event.Threshold
                    
                    self.MatchScoreUpdated.emit((index, event.MatchScore))
                    
                    # Rising Edge (Off -> On)
                    if isMatchNow and not event.IsCurrentlyHeld or \
                       isMatchNow and (time.time() * 1000 - event.TimeOfLastTriggerMs > 5000):
                        self.EventTriggered.emit(event)
                        event.TimeOfLastTriggerMs = int(time.time() * 1000)
                        event.IsCurrentlyHeld = isMatchNow
                
                elif event.SelectedActivationType == ActivationType.ProgessBar:
                    if local_img is None:
                        continue
                    
                    local_img_roi = cropImage(local_img, (event.Roi.XN, event.Roi.YN, event.Roi.WN, event.Roi.HN))
                    event.PercentFilled = estimateProgressBarPercentage(local_img_roi)
                    
                    self.MatchScoreUpdated.emit((index, event.PercentFilled))
                    
                    if event.TriggerWhenMatch:
                        isFilledNow = event.PercentFilled >= event.Threshold
                    else:
                        isFilledNow = event.PercentFilled < event.Threshold
                    
                    # Rising Edge (Off -> On)
                    if isFilledNow and not event.IsCurrentlyHeld or \
                       isFilledNow and (time.time() * 1000 - event.TimeOfLastTriggerMs > 5000):
                        self.EventTriggered.emit(event)
                        event.TimeOfLastTriggerMs = int(time.time() * 1000)
                        event.IsCurrentlyHeld = isFilledNow
            
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

    def __init__(self, hwnd: int, intervalMs: int = 200, parent: Optional[QObject] = None) -> None:
        """
        Initialize the live capture thread.
        
        Args:
            hwnd: Window handle to capture
            intervalMs: Capture interval in milliseconds
            parent: Parent QObject
        """
        super().__init__(parent)
        self.Hwnd: int = hwnd
        self.IntervalMs: int = intervalMs
        self._isRunning: bool = True
        self._imageCount: int = 0

    def run(self) -> None:
        """Main thread execution loop."""
        self._isRunning = True
        while self._isRunning:
            try:
                img = captureWindowByHwnd(self.Hwnd)
                self.ImageCaptured.emit(img)
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
        HwndUpdated: Emitted when the window handle is updated
        CaptureImageReady: Emitted when a capture image is ready
        EventDisabled: Emitted when an event is disabled
        EventFlowChange: Emitted when the flow state changes
        EventFlowHotkeyChange: Emitted when the flow hotkey changes
        EventMatchScoreUpdated: Emitted when a match score is updated
    """
    
    EventAdded = Signal(EventItem)
    EventRemoved = Signal(int)
    HwndUpdated = Signal(object)  # HWND
    CaptureImageReady = Signal(object)  # Image data
    EventDisabled = Signal(int)  # Index of changed event
    EventFlowChange = Signal(bool)  # Flow state
    EventFlowHotkeyChange = Signal(list)  # Flow hotkey list
    EventMatchScoreUpdated = Signal(tuple)  # (index, score)

    def __init__(self) -> None:
        """Initialize the dashboard view model."""
        super().__init__()
        self.EventItems: List[EventItem] = []
        self.CurrentHwnd: Optional[int] = None
        self.LiveThread: Optional[LiveCaptureThread] = None
        self.LastLiveImg: Optional[np.ndarray[Any, Any]] = None
        self.TriggerThread: Optional[TriggerMonitorThread] = None
        
        self.StartSentinel()  # Initialize the sentinel monitoring

    def AddNewEvent(self) -> None:
        """Add a new event to the model."""
        newAction = ActionItem()
        newEvent = EventItem(name="New Event", action=newAction)
        self.EventItems.append(newEvent)
        self.EventAdded.emit(newEvent)

    def DeleteEvent(self, index: int) -> None:
        """
        Delete an event at the specified index.
        
        Args:
            index: Index of the event to delete
        """
        if 0 <= index < len(self.EventItems):
            self.EventItems.pop(index)
            self.EventRemoved.emit(index)

    def FindWindow(self, title: str) -> Optional[int]:
        """
        Find a window by its title.
        
        Args:
            title: Title of the window to find
        
        Returns:
            Window handle if found, None otherwise
        """
        hwnd = findHwndByTitle(title)
        self.CurrentHwnd = hwnd
        self.HwndUpdated.emit(hwnd)
        return hwnd

    def LaunchApp(self, path: str) -> Optional[int]:
        """
        Launch an application from the specified path.
        
        Args:
            path: Path to the executable
        
        Returns:
            Process ID if launched successfully, None otherwise
        """
        if path:
            return launchHwndByExecutable(path)
        return None

    def ResizeTargetWindow(self, width: int, height: int) -> None:
        """
        Resize the target window to the specified dimensions.
        
        Args:
            width: New width in pixels
            height: New height in pixels
        """
        if self.CurrentHwnd:
            ResizeWindow(self.CurrentHwnd, width, height)

    def ToggleCapture(self, active: bool) -> None:
        """
        Toggle live capture on or off.
        
        Args:
            active: True to start capture, False to stop
        """
        if active and self.CurrentHwnd:
            self.StopCapture()
            self.LiveThread = LiveCaptureThread(self.CurrentHwnd)
            self.LiveThread.ImageCaptured.connect(self._HandleImageCaptured)
            
            if self.TriggerThread is not None:
                self.LiveThread.ImageCaptured.connect(self.TriggerThread.SetImage)
            
            self.LiveThread.start()
        else:
            self.StopCapture()

    def _HandleImageCaptured(self, img: np.ndarray[Any, Any]) -> None:
        """
        Handle a captured image.
        
        Args:
            img: Captured image data
        """
        self.LastLiveImg = img
        self.CaptureImageReady.emit(img)

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
            self.TriggerThread.EventTriggered.connect(self._OnEventTriggered)
            self.TriggerThread.EventDisabled.connect(self._OnEventDisabled)
            self.TriggerThread.FlowChanged.connect(self._OnFlowChanged)
            self.TriggerThread.FlowHotkeyChanged.connect(self.EventFlowHotkeyChange)
            self.TriggerThread.MatchScoreUpdated.connect(self.EventMatchScoreUpdated)
            self.TriggerThread.start()

    def _OnEventTriggered(self, event: EventItem) -> None:
        """
        Handle an event trigger.
        
        Args:
            event: Event that was triggered
        """
        print(f"Event Triggered: {event.Name}")
        if self.CurrentHwnd:
            event.Trigger(self.CurrentHwnd)

    def _OnEventDisabled(self, event: EventItem) -> None:
        """
        Handle an event being disabled.
        
        Args:
            event: Event that was disabled
        """
        print(f"Event Disabled: {event.Name}")
        try:
            index = self.EventItems.index(event)
            self.EventDisabled.emit(index)
        except ValueError:
            pass

    def _OnFlowChanged(self, flow: bool) -> None:
        """
        Handle a flow state change.
        
        Args:
            flow: New flow state
        """
        self.EventFlowChange.emit(flow)

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
            
            with open(filePath, 'wb') as f:
                pickle.dump(data_to_save, f)
            
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
            with open(filePath, 'rb') as f:
                data = pickle.load(f)
            
            # --- SMART LOADING LOGIC ---
            loaded_events: List[EventItem] = []
            loaded_hotkey: List[int] = []
            
            if isinstance(data, dict):
                # New Format: Dictionary containing events and settings
                data_dict: Dict[str, Any] = cast(Dict[str, Any], data)
                loaded_events = cast(List[EventItem], data_dict.get("events", []))
                loaded_hotkey = cast(List[int], data_dict.get("settings", []))
                print(f"Loading new format (v{data_dict.get('version', '1.0.0')})")
            else:
                print("Unknown data format in save file.")
                return
            
            # ---------------------------
            # Populate the UI/Model
            if self.TriggerThread is not None:
                self.TriggerThread.SetFlow(False)  # Ensure flow is off during loading
            
            self.EventItems.clear()
            
            for event in loaded_events:
                self.EventItems.append(event)
                if hasattr(self, 'EventAdded'):
                    self.EventAdded.emit(event)
            
            # Apply settings if they exist
            if self.TriggerThread and loaded_hotkey:
                self.TriggerThread.SetFlowHotkey(loaded_hotkey)
        except Exception as e:
            print(f"LoadState Error: {e}")
            raise e

    def EnableEvent(self, event: EventItem) -> None:
        """
        Enable an event.
        
        Args:
            event: Event to enable
        """
        event.Enabled = True
        event.LoopCounter = 0

    def DisableEvent(self, event: EventItem) -> None:
        """
        Disable an event.
        
        Args:
            event: Event to disable
        """
        event.Enabled = False

    def ToggleSentinelFlow(self) -> None:
        """Toggle the sentinel flow state."""
        if self.TriggerThread:
            self.TriggerThread.ToggleFlow()


# =============================================================================
# VIEW CLASSES
# =============================================================================

class ClickableImageLabel(QLabel):
    """
    An image label that emits a signal when clicked with normalized coordinates.
    
    Signals:
        Clicked: Emitted when the label is clicked
    
    Properties:
        NxValue: Normalized X coordinate of the marker
        NyValue: Normalized Y coordinate of the marker
    """
    
    Clicked = Signal(QPoint)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the clickable image label.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.NxValue: Optional[float] = None
        self.NyValue: Optional[float] = None
        self.setMouseTracking(True)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """
        Handle mouse press events.
        
        Args:
            event: Mouse event
        """
        if event.button() == Qt.MouseButton.LeftButton:
            w, h = self.width(), self.height()
            if w > 0 and h > 0:
                self.NxValue = event.position().x() / w
                self.NyValue = event.position().y() / h
                self.Clicked.emit(event.position().toPoint())
                self.update()

    def SetMarkerNormalized(self, nx: float, ny: float) -> None:
        """
        Set the marker position using normalized coordinates.
        
        Args:
            nx: Normalized X coordinate (0.0 to 1.0)
            ny: Normalized Y coordinate (0.0 to 1.0)
        """
        self.NxValue = nx
        self.NyValue = ny
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        """
        Handle paint events to draw the marker.
        
        Args:
            event: Paint event
        """
        super().paintEvent(event)
        
        if self.NxValue is None or self.NyValue is None:
            return
        
        x = int(self.NxValue * self.width())
        y = int(self.NyValue * self.height())
        
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
        CapturedVks: List of captured virtual key codes
    """
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the hotkey capture dialog.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("Capture VK Combo")
        self.setFixedSize(250, 100)
        
        self.CapturedVks: List[int] = []
        self._currentVks: set[int] = set()
        
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
        vk = event.nativeVirtualKey()
        if vk > 0:
            self._currentVks.add(vk)
            self.StatusLabel.setText(f"Holding: {len(self._currentVks)} keys")

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        """
        Handle key release events.
        
        Args:
            event: Key event
        """
        # When keys are released, we finalize the list
        if self._currentVks:
            self.CapturedVks = list(self._currentVks)
            self.accept()


class CropperWidget(QWidget):
    """
    A PySide ROI selector that mimics the behavior of the Tkinter version.
    
    Properties:
        on_crop: Callback function when crop is complete
    """
    
    def __init__(
        self,
        image_data: np.ndarray[Any, Any],
        on_crop: Callable[[np.ndarray[Any, Any], float, float, float, float], None]
    ) -> None:
        """
        Initialize the cropper widget.
        
        Args:
            image_data: Image data to display
            on_crop: Callback function when crop is complete
        """
        super().__init__()
        self.on_crop = on_crop
        self.setMinimumSize(640, 480)  # Give it a starting minimum size
        
        # 1. Setup Layout
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 2. Setup Label
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # This is critical: allows the label to shrink smaller than the image
        self.image_label.setMinimumSize(1, 1)
        
        # 3. Store the Original Pixmap
        self.original_pixmap = self._ndarray2QPixmap(image_data)
        layout.addWidget(self.image_label)
        
        self.setLayout(layout)
        self.showMaximized()
        
        self.rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self.image_label)
        self.origin = QPoint()

    def resizeEvent(self, event: QResizeEvent) -> None:
        """
        Handle resize events to scale the image.
        
        Args:
            event: Resize event
        """
        if not self.original_pixmap.isNull():
            # Scale the original image to fit the current label size
            scaled_pixmap = self.original_pixmap.scaled(
                self.image_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.image_label.setPixmap(scaled_pixmap)
        
        super().resizeEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """
        Handle mouse press events to start selection.
        
        Args:
            event: Mouse event
        """
        if event.button() == Qt.MouseButton.LeftButton:
            self.origin = event.position().toPoint()
            self.rubber_band.setGeometry(QRect(self.origin, QSize()))
            self.rubber_band.show()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """
        Handle mouse move events to update selection.
        
        Args:
            event: Mouse event
        """
        if not self.origin.isNull():
            # Update selection rectangle dynamically
            self.rubber_band.setGeometry(QRect(self.origin, event.position().toPoint()).normalized())

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """
        Handle mouse release events to complete selection.
        
        Args:
            event: Mouse event
        """
        if event.button() == Qt.MouseButton.LeftButton:
            # 1. Get the geometry of the rubber band (Screen Space)
            selectionRect = self.rubber_band.geometry()
            
            # 2. Calculate the scaling ratio
            shownPixmapSize = self.image_label.pixmap().size()
            fullPixmapSize = self.original_pixmap.size()
            fullWidth = fullPixmapSize.width()
            fullHeight = fullPixmapSize.height()
            
            ratioX = fullWidth / shownPixmapSize.width()
            ratioY = fullHeight / shownPixmapSize.height()
            
            # 3. Calculate the actual crop area on the ORIGINAL image
            offsetX = (self.image_label.width() - shownPixmapSize.width()) / 2
            offsetY = (self.image_label.height() - shownPixmapSize.height()) / 2
            
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
            croppedPixmap = self.original_pixmap.copy(realRect)
            cvImage = self._qpixmap2Ndarray(croppedPixmap)
            
            # Passing normalized values to the callback
            self.on_crop(cvImage, normX, normY, normW, normH)
            self.close()

    def _qpixmap2Ndarray(self, pixmap: QPixmap) -> np.ndarray[Any, Any]:
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
        bytes_per_line = image.bytesPerLine()  # This is the "772" in your case
        
        # 2. Get the memoryview
        ptr = image.bits()
        
        # 3. Create a 1D array first
        arr = np.frombuffer(ptr, np.uint8)
        
        # 4. Reshape to (Height, BytesPerLine) to include padding
        # This matches the 169068 size perfectly
        arr = arr.reshape((height, bytes_per_line))
        
        # 5. Crop out the padding
        # We only want the first (width * 3) bytes of every row
        actual_data_width = width * 3
        arr = arr[:, :actual_data_width]
        
        # 6. Final reshape to (Height, Width, Channels)
        arr = arr.reshape((height, width, 3))
        
        # 7. Convert RGB to BGR and return a safe copy
        return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR).copy()

    def _ndarray2QPixmap(self, cv_img: np.ndarray[Any, Any]) -> QPixmap:
        """
        Convert OpenCV BGR array to QPixmap.
        
        Args:
            cv_img: OpenCV BGR array
        
        Returns:
            QPixmap representation
        """
        height, width, _channel = cv_img.shape
        bytes_per_line = 3 * width
        
        # Convert BGR to RGB
        cv_rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        
        # Create QImage
        q_img = QImage(cv_rgb.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
        
        # Important: QImage uses the underlying buffer of the ndarray.
        # We must return a copy as a Pixmap to avoid memory access issues.
        return QPixmap.fromImage(q_img)


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
        self.InitializeComponents()
        self.WireUpBindings()

    def InitializeComponents(self) -> None:
        """Initialize all UI components."""
        self.setWindowTitle("SentinelFlow Dashboard")
        self.resize(1000, 650)
        
        self.MainLayout = QHBoxLayout(self)
        self.MainLayout.setContentsMargins(0, 0, 0, 0)
        self.MainLayout.setSpacing(5)
        
        # Panels
        self.MainLayout.addLayout(self.SetupLeftPanel(), 0)
        self.MainLayout.addLayout(self.SetupCenterPanel(), 1)
        self.MainLayout.addWidget(self.SetupRightPanel())

    def SetupLeftPanel(self) -> QVBoxLayout:
        """Set up the left panel with event management controls."""
        layout = QVBoxLayout()
        
        btnLayout = QHBoxLayout()
        self.BtnAddEvent = QPushButton("+")
        self.BtnDelEvent = QPushButton("-")
        self.BtnAddEvent.setFixedWidth(30)
        self.BtnDelEvent.setFixedWidth(30)
        
        self.BtnSaveEvent = QPushButton("Save")
        self.BtnLoadEvent = QPushButton("Load")
        self.BtnSaveEvent.setFixedWidth(40)
        self.BtnLoadEvent.setFixedWidth(40)
        
        btnLayout.addWidget(self.BtnAddEvent)
        btnLayout.addWidget(self.BtnDelEvent)
        btnLayout.addStretch()
        btnLayout.addWidget(self.BtnSaveEvent)
        btnLayout.addWidget(self.BtnLoadEvent)
        
        self.EventListWidget = QListWidget()
        self.EventListWidget.setFixedWidth(200)
        self.EventListWidget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        
        layout.addLayout(btnLayout)
        layout.addWidget(self.EventListWidget)
        
        # Sentinel Control
        self.BtnStartSentinel = QPushButton("Stop Sentinel")
        self.BtnStartSentinel.setStyleSheet(BUTTON_STYLE_RUNNING)
        
        layout.addWidget(self.BtnStartSentinel)
        
        # for Sentinel Control Hotkey capture dialog
        self.SentinalHotkeyEdit = QLineEdit()
        self.SentinalHotkeyEdit.setReadOnly(True)
        self.SentinalHotkeyBtn = QPushButton("Capture Sentinel Hotkey")
        
        layout.addWidget(self.SentinalHotkeyEdit)
        layout.addWidget(self.SentinalHotkeyBtn)
        
        return layout

    def SetupCenterPanel(self) -> QVBoxLayout:
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
        self.ExePathEdit = QLineEdit(r"C:\Users\HONG\Desktop\frozenthrone1.26\war3.exe -window")
        self.BtnBrowse = QPushButton("Browse")
        self.BtnLaunch = QPushButton("Launch")
        
        exeLayout.addWidget(QLabel("Path:"))
        exeLayout.addWidget(self.ExePathEdit)
        exeLayout.addWidget(self.BtnBrowse)
        exeLayout.addWidget(self.BtnLaunch)
        groupMasterLayout.addLayout(exeLayout)
        
        # Row 2: Proc
        procLayout = QHBoxLayout()
        self.TitleEdit = QLineEdit("Warcraft III")
        self.BtnFindHwnd = QPushButton("Find Process")
        self.PidLabel = QLabel("Pid: -")
        
        procLayout.addWidget(QLabel("Title:"))
        procLayout.addWidget(self.TitleEdit)
        procLayout.addWidget(self.BtnFindHwnd)
        procLayout.addWidget(self.PidLabel)
        groupMasterLayout.addLayout(procLayout)
        
        # Row 3: Metrics
        resLayout = QHBoxLayout()
        self.ResizeWidthEdit = QLineEdit("640")
        self.ResizeHeightEdit = QLineEdit("480")
        self.BtnResize = QPushButton("Resize Window")
        
        resLayout.addWidget(QLabel("W:"))
        resLayout.addWidget(self.ResizeWidthEdit)
        resLayout.addWidget(QLabel("H:"))
        resLayout.addWidget(self.ResizeHeightEdit)
        resLayout.addWidget(self.BtnResize)
        groupMasterLayout.addLayout(resLayout)
        
        groupMasterLayout.addStretch(1)
        mgmtGroupBox.setLayout(groupMasterLayout)
        
        # Live View
        self.BtnLiveCapture = QPushButton("Start Live Capture")
        self.BtnLiveCapture.setCheckable(True)
        
        self.LiveImageLabel = ClickableImageLabel()
        self.LiveImageLabel.setScaledContents(True)
        self.LiveImageLabel.setMinimumSize(640, 480)
        self.LiveImageLabel.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.LiveImageLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Interaction
        interactLayout = QHBoxLayout()
        self.KeystrokeEdit = QLineEdit()
        self.BtnSendKeystroke = QPushButton("Send Key")
        
        self.MouseXEdit = QLineEdit()
        self.MouseYEdit = QLineEdit()
        self.BtnSendClick = QPushButton("Send Click")
        
        interactLayout.addWidget(self.KeystrokeEdit)
        interactLayout.addWidget(self.BtnSendKeystroke)
        interactLayout.addSpacing(10)
        interactLayout.addWidget(QLabel("X:"))
        interactLayout.addWidget(self.MouseXEdit)
        interactLayout.addWidget(QLabel("Y:"))
        interactLayout.addWidget(self.MouseYEdit)
        interactLayout.addWidget(self.BtnSendClick)
        
        layout.addWidget(mgmtGroupBox)
        layout.addWidget(self.BtnLiveCapture)
        layout.addWidget(self.LiveImageLabel)
        layout.addLayout(interactLayout)
        
        return layout

    def SetupRightPanel(self) -> QWidget:
        """Set up the right panel with event configuration controls."""
        # Create a container to fix the width as discussed
        rightPanelContainer = QWidget()
        rightPanelContainer.setFixedWidth(350)
        
        layout = QVBoxLayout(rightPanelContainer)
        
        self.EventSettingsHeader = QLabel("<b>Event Settings</b>")
        
        # Event Properties
        self.EventNameEdit = QLineEdit()
        self.EventNameEdit.setEnabled(False)
        
        self.ActivationDropdown = QComboBox()
        self.ActivationDropdown.setEnabled(False)
        self.ActivationDropdown.addItems([at.name for at in ActivationType])
        
        # hotkey capture widget
        self.ActivationHotkeyWidget = QWidget()
        self.ActivationHotkeyLayout = QHBoxLayout()
        self.ActivationHotkeyLayout.addWidget(QLabel("Hotkey:"))
        self.ActivationHotkeyEdit = QLineEdit()
        self.ActivationHotkeyEdit.setReadOnly(True)
        self.ActivationHotkeyLayout.addWidget(self.ActivationHotkeyEdit)
        self.ActivationHotkeyBtn = QPushButton("Capture")
        self.ActivationHotkeyLayout.addWidget(self.ActivationHotkeyBtn)
        self.ActivationHotkeyBtn.setEnabled(False)
        self.ActivationHotkeyWidget.setLayout(self.ActivationHotkeyLayout)
        self.ActivationHotkeyWidget.hide()
        
        # loop and interval widgets
        self.LoopWidget = QWidget()
        self.LoopWidgetLayout = QHBoxLayout()
        
        self.LoopCountLayout = QVBoxLayout()
        self.LoopCountLabel = QLabel("Count:")
        self.LoopCountEdit = QLineEdit("1")
        self.LoopCountLayout.addWidget(self.LoopCountLabel)
        self.LoopCountLayout.addWidget(self.LoopCountEdit)
        
        self.LoopIntervalLayout = QVBoxLayout()
        self.LoopIntervalLabel = QLabel("Interval (ms):")
        self.LoopIntervalEdit = QLineEdit("1000")
        self.LoopIntervalLayout.addWidget(self.LoopIntervalLabel)
        self.LoopIntervalLayout.addWidget(self.LoopIntervalEdit)
        
        self.LoopWidgetLayout.addLayout(self.LoopCountLayout)
        self.LoopWidgetLayout.addLayout(self.LoopIntervalLayout)
        self.LoopWidget.setLayout(self.LoopWidgetLayout)
        self.LoopCountEdit.setEnabled(False)
        self.LoopIntervalEdit.setEnabled(False)
        self.LoopWidget.hide()
        
        # Roi widget
        self.RoiWidget = QWidget()
        self.RoiWidgetLayout = QHBoxLayout()
        self.RoiWidgetLayoutInner = QVBoxLayout()
        
        self.RoiXEditLayout = QHBoxLayout()
        self.RoiYEditLayout = QHBoxLayout()
        self.RoiWEditLayout = QHBoxLayout()
        self.RoiHEditLayout = QHBoxLayout()
        
        self.RoiXEdit = QLineEdit("0.0")
        self.RoiYEdit = QLineEdit("0.0")
        self.RoiWEdit = QLineEdit("1.0")
        self.RoiHEdit = QLineEdit("1.0")
        
        self.RoiXEditLayout.addWidget(QLabel("X:"))
        self.RoiXEditLayout.addWidget(self.RoiXEdit)
        self.RoiYEditLayout.addWidget(QLabel("Y:"))
        self.RoiYEditLayout.addWidget(self.RoiYEdit)
        self.RoiWEditLayout.addWidget(QLabel("W:"))
        self.RoiWEditLayout.addWidget(self.RoiWEdit)
        self.RoiHEditLayout.addWidget(QLabel("H:"))
        self.RoiHEditLayout.addWidget(self.RoiHEdit)
        
        self.RoiWidgetLayoutInner.addWidget(QLabel("Roi:"))
        self.RoiWidgetLayoutInner.addLayout(self.RoiXEditLayout)
        self.RoiWidgetLayoutInner.addLayout(self.RoiYEditLayout)
        self.RoiWidgetLayoutInner.addLayout(self.RoiWEditLayout)
        self.RoiWidgetLayoutInner.addLayout(self.RoiHEditLayout)
        
        self.RoiButtonLayout = QVBoxLayout()
        self.RoiButtonLayout.setContentsMargins(0, 0, 0, 0)
        self.RoiButton = QPushButton("Select from Image")
        self.RoiButton.setFixedSize(150, 150)
        self.RoiButtonLayout.addWidget(self.RoiButton)
        
        self.RoiWidgetLayout.addLayout(self.RoiWidgetLayoutInner)
        self.RoiWidgetLayout.addLayout(self.RoiButtonLayout)
        
        self.RoiButton.setEnabled(False)
        self.RoiWidget.setLayout(self.RoiWidgetLayout)
        self.RoiXEdit.setReadOnly(True)
        self.RoiYEdit.setReadOnly(True)
        self.RoiWEdit.setReadOnly(True)
        self.RoiHEdit.setReadOnly(True)
        self.RoiWidget.hide()
        
        # Threshold widget
        self.ThresholdWidget = QWidget()
        self.ThresholdWidgetLayout = QVBoxLayout()
        
        self.ThresholdWidgetMatchScoreLayout = QHBoxLayout()
        self.ThresholdMatchScoreLabel = QLabel("0.000")
        self.ThresholdWidgetMatchScoreLayout.addWidget(QLabel("Match Score:"))
        self.ThresholdWidgetMatchScoreLayout.addWidget(self.ThresholdMatchScoreLabel)
        
        self.ThresholdWidgetMatchScoreBtnLayout = QHBoxLayout()
        self.ThresholdMatchScoreCopyBtn = QPushButton("↓")
        self.ThresholdMatchScoreCopyBtn.setFixedWidth(30)
        self.ThresholdWidgetMatchScoreBtnLayout.addWidget(self.ThresholdMatchScoreCopyBtn)
        
        self.ThresholdWidgetThresholdLayout = QHBoxLayout()
        self.ThresholdWidgetThresholdLayout.addWidget(QLabel("Threshold:"))
        self.ThresholdEdit = QLineEdit("0.99")
        self.ThresholdWidgetThresholdLayout.addWidget(self.ThresholdEdit)
        
        self.ThresholdWidgetLayout.addLayout(self.ThresholdWidgetMatchScoreLayout)
        self.ThresholdWidgetLayout.addLayout(self.ThresholdWidgetMatchScoreBtnLayout)
        self.ThresholdWidgetLayout.addLayout(self.ThresholdWidgetThresholdLayout)
        self.ThresholdWidget.setLayout(self.ThresholdWidgetLayout)
        self.ThresholdEdit.setEnabled(False)
        self.ThresholdWidget.hide()
        
        # Trigger Type Specific Widgets
        self.TriggerWhenMatchLayout = QHBoxLayout()
        self.TriggerWhenMatchWidget = QWidget()
        self.TriggerWhenMatchCheckbox = QCheckBox("Trigger When Match")
        self.TriggerWhenMatchCheckbox.setEnabled(False)
        self.TriggerWhenMatchLayout.addWidget(self.TriggerWhenMatchCheckbox)
        self.TriggerWhenMatchWidget.setLayout(self.TriggerWhenMatchLayout)
        self.TriggerWhenMatchWidget.hide()
        
        # Action Sequence Properties
        self.ActionNameLabel = QLabel("<b>Action Sequence</b>")
        
        # The actual list of MacroSteps
        self.MacroStepListWidgetLayout = QHBoxLayout()
        self.MacroStepListWidget = QListWidget()
        self.MacroStepListWidget.setMinimumHeight(200)
        
        self.BtnMoveLayout = QVBoxLayout()
        self.BtnMoveUp = QPushButton("↑")
        self.BtnMoveDown = QPushButton("↓")
        self.BtnMoveUp.setFixedWidth(30)
        self.BtnMoveDown.setFixedWidth(30)
        self.BtnMoveUp.setEnabled(False)
        self.BtnMoveDown.setEnabled(False)
        
        self.MacroStepListWidgetLayout.addWidget(self.MacroStepListWidget)
        self.BtnMoveLayout.addWidget(self.BtnMoveUp)
        self.BtnMoveLayout.addWidget(self.BtnMoveDown)
        self.MacroStepListWidgetLayout.addLayout(self.BtnMoveLayout)
        
        self.stepDropDown = QComboBox()
        self.stepDropDown.addItems([mt.name for mt in InputType])
        self.stepDropDown.setEnabled(False)
        
        # Buttons for Step Management
        stepButtonLayout = QHBoxLayout()
        self.BtnAddStep = QPushButton("Add Step")
        self.BtnDelStep = QPushButton("Remove Step")
        self.BtnAddStep.setEnabled(False)
        self.BtnDelStep.setEnabled(False)
        stepButtonLayout.addWidget(self.BtnAddStep)
        stepButtonLayout.addWidget(self.BtnDelStep)
        
        # Add to Layout
        layout.addWidget(self.EventSettingsHeader)
        layout.addWidget(QLabel("Event Name:"))
        layout.addWidget(self.EventNameEdit)
        layout.addWidget(QLabel("Trigger Type:"))
        layout.addWidget(self.ActivationDropdown)
        layout.addWidget(self.ActivationHotkeyWidget)
        layout.addWidget(self.LoopWidget)
        layout.addWidget(self.RoiWidget)
        layout.addWidget(self.ThresholdWidget)
        layout.addWidget(self.TriggerWhenMatchWidget)
        layout.addWidget(self.CreateHorizontalLine())  # Optional visual separator
        layout.addWidget(self.ActionNameLabel)
        layout.addLayout(self.MacroStepListWidgetLayout)
        layout.addWidget(self.stepDropDown)
        layout.addLayout(stepButtonLayout)
        layout.addStretch()
        
        return rightPanelContainer

    def CreateHorizontalLine(self) -> QFrame:
        """Create a horizontal separator line."""
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        return line

    def WireUpBindings(self) -> None:
        """Connect UI signals to ViewModel methods and ViewModel signals to UI updates."""
        # --- View to ViewModel ---
        self.BtnAddEvent.clicked.connect(self.ViewModel.AddNewEvent)
        self.BtnDelEvent.clicked.connect(lambda: self.ViewModel.DeleteEvent(self.EventListWidget.currentRow()))
        self.BtnStartSentinel.clicked.connect(self.ViewModel.ToggleSentinelFlow)
        self.BtnSaveEvent.clicked.connect(self.OnSaveEvent)
        self.BtnLoadEvent.clicked.connect(self.OnLoadEvent)
        self.BtnFindHwnd.clicked.connect(lambda: self.ViewModel.FindWindow(self.TitleEdit.text().strip()))
        self.BtnBrowse.clicked.connect(self.OnBrowseExecutable)
        self.BtnLaunch.clicked.connect(self.OnLaunchExecutable)
        self.BtnResize.clicked.connect(self.OnResizeRequested)
        self.BtnLiveCapture.toggled.connect(self.OnToggleCapture)
        self.BtnMoveUp.clicked.connect(lambda: self.MoveStep(-1))
        self.BtnMoveDown.clicked.connect(lambda: self.MoveStep(1))
        self.BtnAddStep.clicked.connect(self.OnAddStepClicked)
        self.BtnDelStep.clicked.connect(self.OnRemoveStepClicked)
        self.ActivationHotkeyBtn.clicked.connect(self.OnCaptureHotkey)
        self.RoiButton.clicked.connect(self.OnSelectRoi)
        self.SentinalHotkeyBtn.clicked.connect(self.OnCaptureSentinelHotkey)
        
        # Interaction
        self.LiveImageLabel.Clicked.connect(self.OnImageClicked)
        self.BtnSendClick.clicked.connect(self.OnSendMouseClick)
        self.BtnSendKeystroke.clicked.connect(self.OnSendKeystroke)
        self.MouseXEdit.textChanged.connect(self.OnManualCoordsChanged)
        self.MouseYEdit.textChanged.connect(self.OnManualCoordsChanged)
        self.ThresholdMatchScoreCopyBtn.clicked.connect(self.OnCopyMatchScoreToThreshold)
        
        # Property Editing
        self.EventListWidget.currentItemChanged.connect(self.OnSelectionChanged)
        self.EventListWidget.itemChanged.connect(self.OnEventItemChanged)
        self.EventNameEdit.editingFinished.connect(self.OnCommitEventName)
        self.ActivationDropdown.currentIndexChanged.connect(self.OnCommitActivationType)
        self.LoopCountEdit.editingFinished.connect(self.OnCommitLoopCount)
        self.LoopIntervalEdit.editingFinished.connect(self.OnCommitLoopInterval)
        self.ThresholdEdit.editingFinished.connect(self.OnCommitThreshold)
        self.TriggerWhenMatchCheckbox.stateChanged.connect(self.OnCommitTriggerWhenMatch)
        
        # --- ViewModel to View ---
        self.ViewModel.EventAdded.connect(self.UpdateUiAddEvent)
        self.ViewModel.EventRemoved.connect(self.UpdateUiRemoveEvent)
        self.ViewModel.HwndUpdated.connect(self.UpdateUiHwndInfo)
        self.ViewModel.CaptureImageReady.connect(self.UpdateUiImage)
        self.ViewModel.EventDisabled.connect(self.UpdateUiEventDisabled)
        self.ViewModel.EventFlowChange.connect(self.UpdateUiSentinelFlow)
        self.ViewModel.EventFlowHotkeyChange.connect(self.UpdateUiSentinelHotkey)
        self.ViewModel.EventMatchScoreUpdated.connect(self.UpdateUiEventMatchScore)

    def OnSaveEvent(self) -> None:
        """Handle save event button click."""
        # Updated filter to show Data/Pickle files instead of JSON
        filePath, _ = QFileDialog.getSaveFileName(
            self,
            "Save Macro Configuration",
            "",
            "Data Files (*.dat);;Pickle Files (*.pkl);;All Files (*)"
        )
        
        if filePath:
            try:
                # ViewModel.SaveState now handles binary Pickle serialization
                self.ViewModel.SaveState(filePath)
                QMessageBox.information(self, "Success", "Configuration saved successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save file: {e}")

    def OnLoadEvent(self) -> None:
        """Handle load event button click."""
        # Updated filter to look for binary files
        filePath, _ = QFileDialog.getOpenFileName(
            self,
            "Load Macro Configuration",
            "",
            "Data Files (*.dat);;Pickle Files (*.pkl);;All Files (*)"
        )
        
        if filePath:
            try:
                # Clear existing UI list before loading new data
                self.EventListWidget.clear()
                self.MacroStepListWidget.clear()
                
                # ViewModel.LoadState now handles binary Pickle deserialization
                self.ViewModel.LoadState(filePath)
                QMessageBox.information(self, "Success", "Configuration loaded successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load file: {e}")

    def OnBrowseExecutable(self) -> None:
        """Handle browse executable button click."""
        path, _ = QFileDialog.getOpenFileName(self, "Select EXE", "", "Executables (*.exe)")
        if path:
            self.ExePathEdit.setText(path)

    def OnLaunchExecutable(self) -> None:
        """Handle launch executable button click."""
        pid = self.ViewModel.LaunchApp(self.ExePathEdit.text().strip())
        if pid:
            QMessageBox.information(self, "Success", f"Launched PID: {pid}")

    def OnResizeRequested(self) -> None:
        """Handle resize window button click."""
        try:
            w, h = int(self.ResizeWidthEdit.text()), int(self.ResizeHeightEdit.text())
            self.ViewModel.ResizeTargetWindow(w, h)
        except ValueError:
            QMessageBox.warning(self, "Error", "Invalid dimensions.")

    def OnToggleCapture(self, checked: bool) -> None:
        """
        Handle live capture toggle.
        
        Args:
            checked: Whether capture is enabled
        """
        if checked and not self.ViewModel.CurrentHwnd:
            self.BtnLiveCapture.setChecked(False)
            QMessageBox.warning(self, "Error", "Please find a window first.")
            return
        
        self.ViewModel.ToggleCapture(checked)

    def OnAddStepClicked(self) -> None:
        """Handle add step button click."""
        item = self.EventListWidget.currentItem()
        if item:
            eventObj: EventItem = item.data(Qt.ItemDataRole.UserRole)
            if eventObj.AssignedAction:
                stepTypeName = self.stepDropDown.currentText()
                if stepTypeName in InputType.__members__:
                    stepType = InputType[stepTypeName]
                    
                    # Create a default step based on type
                    newStep = None
                    
                    if stepType == InputType.Mouse:
                        try:
                            nx, ny = float(self.MouseXEdit.text()), float(self.MouseYEdit.text())
                            newStep = MacroStep(InputType.Mouse, (nx, ny), f"Click at ({nx:.7f}, {ny:.7f})")
                        except ValueError:
                            QMessageBox.warning(self, "Error", "Invalid coordinates.")
                            return
                    
                    elif stepType == InputType.Keyboard:
                        dialog = HotkeyCaptureDialog(self)
                        if dialog.exec() == QDialog.DialogCode.Accepted:
                            # We take the first key from the captured list
                            if dialog.CapturedVks:
                                vk = dialog.CapturedVks[0]
                                newStep = MacroStep(InputType.Keyboard, vk, f"Press \"{KeyNameFromVk(vk)}\"")
                            else:
                                return
                        else:
                            return
                    
                    elif stepType == InputType.Delay:
                        ms, ok = QInputDialog.getInt(self, "Add Delay", "Milliseconds (ms):", 100, 1, 60000, 10)
                        if ok:
                            newStep = MacroStep(InputType.Delay, ms, f"Wait {ms}ms")
                        else:
                            return
                    
                    if newStep is not None:
                        eventObj.AssignedAction.AddStep(newStep)
                        self.RefreshMacroStepList(eventObj.AssignedAction)

    def OnRemoveStepClicked(self) -> None:
        """Handle remove step button click."""
        currentRow = self.MacroStepListWidget.currentRow()
        item = self.EventListWidget.currentItem()
        
        if item and currentRow >= 0:
            eventObj: EventItem = item.data(Qt.ItemDataRole.UserRole)
            if eventObj.AssignedAction:
                eventObj.AssignedAction.RemoveStep(currentRow)
                self.RefreshMacroStepList(eventObj.AssignedAction)

    def OnCaptureHotkey(self) -> None:
        """Handle capture hotkey button click."""
        item = self.EventListWidget.currentItem()
        if not item:
            return
        
        eventObj: EventItem = item.data(Qt.ItemDataRole.UserRole)
        dialog = HotkeyCaptureDialog(self)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            eventObj.ActivationVkList = dialog.CapturedVks
            # Show the raw VKs on the button for debugging/clarity
            self.ActivationHotkeyEdit.setText(", ".join(map(KeyNameFromVk, eventObj.ActivationVkList)))

    def OnSelectRoi(self) -> None:
        """Handle select ROI button click."""
        if self.ViewModel.LastLiveImg is None:
            # Handle the case where there is no image
            QMessageBox.warning(self, "Error", "Please start the capture before selecting an ROI.")
            return
        
        self.cropper = CropperWidget(self.ViewModel.LastLiveImg, self.handleNewCrop)
        self.cropper.show()

    def handleNewCrop(
        self,
        cv_img: np.ndarray[Any, Any],
        normX: float,
        normY: float,
        normW: float,
        normH: float
    ) -> None:
        """
        Handle a new crop selection.
        
        Args:
            cv_img: Cropped image data
            normX: Normalized X coordinate
            normY: Normalized Y coordinate
            normW: Normalized width
            normH: Normalized height
        """
        # set model
        item = self.EventListWidget.currentItem()
        if item:
            eventObj: EventItem = item.data(Qt.ItemDataRole.UserRole)
            eventObj.TemplateImage = cv_img
            eventObj.Roi = RectangleRegion(normX, normY, normW, normH)
            
            # set view
            self.setButtonWithImage(self.RoiButton, cv_img)
            self.RoiXEdit.setText(f"{normX:.4f}")
            self.RoiYEdit.setText(f"{normY:.4f}")
            self.RoiWEdit.setText(f"{normW:.4f}")
            self.RoiHEdit.setText(f"{normH:.4f}")

    def setButtonWithImage(self, button: QPushButton, cv_img: np.ndarray[Any, Any]) -> None:
        """
        Set a button's icon to display an image.
        
        Args:
            button: Button to update
            cv_img: Image data to display
        """
        height, width, _channel = cv_img.shape
        bytesPerLine = 3 * width
        cv_rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        q_img = QImage(cv_rgb.data, width, height, bytesPerLine, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(q_img)
        icon = QIcon(pixmap)
        button.setIcon(icon)
        button.setIconSize(button.size())
        button.setText("")

    def OnCaptureSentinelHotkey(self) -> None:
        """Handle capture sentinel hotkey button click."""
        dialog = HotkeyCaptureDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if self.ViewModel.TriggerThread is not None:
                self.ViewModel.TriggerThread.SetFlowHotkey(dialog.CapturedVks)

    def OnImageClicked(self, pos: QPoint) -> None:
        """
        Handle image click events.
        
        Args:
            pos: Click position
        """
        nx = float(pos.x()) / self.LiveImageLabel.width()
        ny = float(pos.y()) / self.LiveImageLabel.height()
        self.MouseXEdit.setText(f"{nx:.7f}")
        self.MouseYEdit.setText(f"{ny:.7f}")

    def OnManualCoordsChanged(self) -> None:
        """Handle manual coordinate changes."""
        try:
            nx = float(self.MouseXEdit.text()) if self.MouseXEdit.text() else 0.0
            ny = float(self.MouseYEdit.text()) if self.MouseYEdit.text() else 0.0
            self.LiveImageLabel.SetMarkerNormalized(nx, ny)
        except ValueError:
            pass

    def OnCopyMatchScoreToThreshold(self) -> None:
        """Handle copy match score to threshold button click."""
        scoreText = self.ThresholdMatchScoreLabel.text()
        self.ThresholdEdit.setText(scoreText)

    def OnSendMouseClick(self) -> None:
        """Handle send mouse click button click."""
        if self.ViewModel.CurrentHwnd:
            try:
                nx, ny = float(self.MouseXEdit.text()), float(self.MouseYEdit.text())
                sendMouseClickToWindow(self.ViewModel.CurrentHwnd, nx, ny)
            except ValueError:
                QMessageBox.warning(self, "Error", "Invalid coordinates.")

    def OnSendKeystroke(self) -> None:
        """Handle send keystroke button click."""
        keyName = self.KeystrokeEdit.text().strip()
        if keyName and self.ViewModel.CurrentHwnd:
            vk = vkFromKeyName(keyName)
            if vk:
                sendKeystrokeToWindow(self.ViewModel.CurrentHwnd, vk)
            else:
                QMessageBox.warning(self, "Error", f"Unknown key: {keyName}")

    def OnSelectionChanged(self, current: Optional[QListWidgetItem], previous: Optional[QListWidgetItem]) -> None:
        """
        Handle event selection changes.
        
        Args:
            current: Currently selected item
            previous: Previously selected item
        """
        if not current:
            self.EventNameEdit.clear()
            self.MacroStepListWidget.clear()
            self.EventNameEdit.setEnabled(False)
            self.ActivationDropdown.setEnabled(False)
            self.ActivationHotkeyBtn.setEnabled(False)
            self.LoopCountEdit.setEnabled(False)
            self.LoopIntervalEdit.setEnabled(False)
            self.stepDropDown.setEnabled(False)
            self.BtnAddStep.setEnabled(False)
            self.BtnDelStep.setEnabled(False)
            self.BtnMoveUp.setEnabled(False)
            self.BtnMoveDown.setEnabled(False)
            self.ThresholdEdit.setEnabled(False)
            self.TriggerWhenMatchCheckbox.setEnabled(False)
            self.RoiButton.setEnabled(False)
            return
        
        eventObj: EventItem = current.data(Qt.ItemDataRole.UserRole)
        self.EventNameEdit.setText(eventObj.Name)
        self.EventNameEdit.setEnabled(True)
        
        activation = eventObj.SelectedActivationType
        typeName = activation.name if hasattr(activation, 'name') else str(activation)
        idx = self.ActivationDropdown.findText(typeName)
        
        if idx >= 0:
            self.ActivationDropdown.setCurrentIndex(idx)
        
        self.ActivationDropdown.setEnabled(True)
        self.ActivationHotkeyEdit.setText(", ".join(map(KeyNameFromVk, eventObj.ActivationVkList)))
        self.ActivationHotkeyBtn.setEnabled(True)
        
        self.LoopCountEdit.setText(str(eventObj.LoopCount))
        self.LoopIntervalEdit.setText(str(eventObj.IntervalMs))
        self.LoopCountEdit.setEnabled(True)
        self.LoopIntervalEdit.setEnabled(True)
        
        self.RoiXEdit.setText(f"{eventObj.Roi.XN:.4f}")
        self.RoiYEdit.setText(f"{eventObj.Roi.YN:.4f}")
        self.RoiWEdit.setText(f"{eventObj.Roi.WN:.4f}")
        self.RoiHEdit.setText(f"{eventObj.Roi.HN:.4f}")
        
        if eventObj.TemplateImage is not None:
            self.setButtonWithImage(self.RoiButton, eventObj.TemplateImage)
        else:
            self.RoiButton.setIcon(QIcon())  # Optionally clear the icon if no image
            self.RoiButton.setText("Select from Image")
        
        self.RoiButton.setEnabled(True)
        self.ThresholdEdit.setText(f"{eventObj.Threshold}")
        self.ThresholdEdit.setEnabled(True)
        self.TriggerWhenMatchCheckbox.setChecked(eventObj.TriggerWhenMatch)
        self.TriggerWhenMatchCheckbox.setEnabled(True)
        
        self.RefreshMacroStepList(eventObj.AssignedAction)
        self.stepDropDown.setEnabled(True)
        self.BtnAddStep.setEnabled(True)
        self.BtnDelStep.setEnabled(True)
        self.BtnMoveUp.setEnabled(True)
        self.BtnMoveDown.setEnabled(True)

    def OnEventItemChanged(self, item: QListWidgetItem) -> None:
        """
        Handle event item changes (renaming, check state).
        
        Args:
            item: Changed item
        """
        # ui
        eventObj: EventItem = item.data(Qt.ItemDataRole.UserRole)
        if not eventObj:
            return
        
        # model
        if item.checkState() == Qt.CheckState.Checked:
            self.ViewModel.EnableEvent(eventObj)
        else:
            self.ViewModel.DisableEvent(eventObj)

    def RefreshMacroStepList(self, actionObj: ActionItem) -> None:
        """
        Refresh the macro step list UI.
        
        Args:
            actionObj: Action containing the steps
        """
        self.MacroStepListWidget.clear()
        
        for step in actionObj.MacroSteps:
            # Check if it's a dict (raw data) or an object
            description = ""
            if isinstance(step, dict):
                description = cast(Dict[str, Any], step).get("Description", "Unknown Step")
            else:
                description = step.Description
            
            item = QListWidgetItem(description)
            item.setData(Qt.ItemDataRole.UserRole, step)  # Store the step data/object
            self.MacroStepListWidget.addItem(item)

    def OnCommitEventName(self) -> None:
        """Commit event name changes."""
        item = self.EventListWidget.currentItem()
        if item:
            eventObj: EventItem = item.data(Qt.ItemDataRole.UserRole)
            newName = self.EventNameEdit.text().strip()
            if newName:
                eventObj.Name = newName
                item.setText(newName)

    def OnCommitActivationType(self, index: int) -> None:
        """
        Commit activation type changes.
        
        Args:
            index: Selected index
        """
        item = self.EventListWidget.currentItem()
        if item and index >= 0:
            eventObj: EventItem = item.data(Qt.ItemDataRole.UserRole)
            typeName = self.ActivationDropdown.currentText()
            # Update via the new property name
            eventObj.SelectedActivationType = ActivationType[typeName]
            
            if eventObj.SelectedActivationType == ActivationType.Hotkey:
                self.ActivationHotkeyWidget.show()
            else:
                self.ActivationHotkeyWidget.hide()
            
            if eventObj.SelectedActivationType == ActivationType.Loop:
                self.LoopWidget.show()
            else:
                self.LoopWidget.hide()
            
            if eventObj.SelectedActivationType == ActivationType.ImageMatchRoi:
                self.RoiWidget.show()
                self.ThresholdWidget.show()
                self.TriggerWhenMatchWidget.show()
            elif eventObj.SelectedActivationType == ActivationType.ProgessBar:
                self.RoiWidget.show()
                self.ThresholdWidget.show()
                self.TriggerWhenMatchWidget.show()
            else:
                self.RoiWidget.hide()
                self.ThresholdWidget.hide()
                self.TriggerWhenMatchWidget.hide()

    def OnCommitLoopCount(self) -> None:
        """Commit loop count changes."""
        item = self.EventListWidget.currentItem()
        if item:
            eventObj: EventItem = item.data(Qt.ItemDataRole.UserRole)
            try:
                count = int(self.LoopCountEdit.text())
                eventObj.LoopCount = count
            except ValueError:
                QMessageBox.warning(self, "Error", "Invalid loop count.")

    def OnCommitLoopInterval(self) -> None:
        """Commit loop interval changes."""
        item = self.EventListWidget.currentItem()
        if item:
            eventObj: EventItem = item.data(Qt.ItemDataRole.UserRole)
            try:
                interval = int(self.LoopIntervalEdit.text())
                eventObj.IntervalMs = interval
            except ValueError:
                QMessageBox.warning(self, "Error", "Invalid interval.")

    def OnCommitThreshold(self) -> None:
        """Commit threshold changes."""
        item = self.EventListWidget.currentItem()
        if item:
            eventObj: EventItem = item.data(Qt.ItemDataRole.UserRole)
            try:
                threshold = float(self.ThresholdEdit.text())
                eventObj.Threshold = threshold
            except ValueError:
                QMessageBox.warning(self, "Error", "Invalid threshold.")

    def OnCommitTriggerWhenMatch(self, state: int) -> None:
        """
        Commit trigger when match changes.
        
        Args:
            state: Check state
        """
        item = self.EventListWidget.currentItem()
        if item:
            eventObj: EventItem = item.data(Qt.ItemDataRole.UserRole)
            eventObj.TriggerWhenMatch = (state == Qt.CheckState.Checked)

    def MoveStep(self, direction: int) -> None:
        """
        Move a step up or down in the list.
        
        Args:
            direction: -1 for Up, 1 for Down
        """
        # 1. Get current selection
        currentRow = self.MacroStepListWidget.currentRow()
        if currentRow == -1:
            return
        
        # 2. Calculate target row and check boundaries
        targetRow = currentRow + direction
        if targetRow < 0 or targetRow >= self.MacroStepListWidget.count():
            return
        
        # 3. Get the Action object from the selected Event
        eventItem = self.EventListWidget.currentItem()
        if not eventItem:
            return
        
        eventObj: EventItem = eventItem.data(Qt.ItemDataRole.UserRole)
        steps = eventObj.AssignedAction.MacroSteps
        
        # 4. Swap in the Python List (The Data Model)
        steps[currentRow], steps[targetRow] = steps[targetRow], steps[currentRow]
        
        # 5. Swap in the UI (The View)
        # We take the item out and re-insert it at the new position
        item = self.MacroStepListWidget.takeItem(currentRow)
        self.MacroStepListWidget.insertItem(targetRow, item)
        
        # 6. Keep the moved item selected so the user can click multiple times
        self.MacroStepListWidget.setCurrentRow(targetRow)

    def UpdateUiAddEvent(self, eventObj: EventItem) -> None:
        """
        Update UI when an event is added.
        
        Args:
            eventObj: Added event
        """
        item = QListWidgetItem(eventObj.Name)
        item.setData(Qt.ItemDataRole.UserRole, eventObj)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Checked if eventObj.Enabled else Qt.CheckState.Unchecked)
        self.EventListWidget.addItem(item)

    def UpdateUiRemoveEvent(self, index: int) -> None:
        """
        Update UI when an event is removed.
        
        Args:
            index: Index of removed event
        """
        self.EventListWidget.takeItem(index)

    def UpdateUiHwndInfo(self, hwnd: Optional[int]) -> None:
        """
        Update UI with window handle information.
        
        Args:
            hwnd: Window handle
        """
        if hwnd:
            self.PidLabel.setText(f"PID: {findPidByHwnd(hwnd)}")
        else:
            self.PidLabel.setText("PID: -")
            QMessageBox.warning(self, "Error", "Window not found.")

    def UpdateUiImage(self, img: Optional[np.ndarray[Any, Any]]) -> None:
        """
        Update UI with a new image.
        
        Args:
            img: Image data to display
        """
        if img is not None:
            h, w, ch = img.shape
            qImg = QImage(img.data, w, h, ch * w, QImage.Format.Format_BGR888)
            pix = QPixmap.fromImage(qImg).scaled(
                self.LiveImageLabel.width(), self.LiveImageLabel.height(),
                Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            self.LiveImageLabel.setPixmap(pix)
        else:
            self.LiveImageLabel.clear()

    def UpdateUiEventDisabled(self, index: int) -> None:
        """
        Update UI when an event is disabled.
        
        Args:
            index: Index of disabled event
        """
        item = self.EventListWidget.item(index)
        if item:
            eventObj: EventItem = item.data(Qt.ItemDataRole.UserRole)
            # Update the check state to reflect Enabled status
            item.setCheckState(Qt.CheckState.Checked if eventObj.Enabled else Qt.CheckState.Unchecked)

    def UpdateUiSentinelFlow(self, isRunning: bool) -> None:
        """
        Update UI when sentinel flow state changes.
        
        Args:
            isRunning: New flow state
        """
        if isRunning:
            # State: RUNNING -> Provide option to STOP
            self.BtnStartSentinel.setText("Stop Sentinel")
            self.BtnStartSentinel.setStyleSheet(BUTTON_STYLE_RUNNING)
        else:
            # State: IDLE -> Provide option to START
            self.BtnStartSentinel.setText("Start Sentinel")
            self.BtnStartSentinel.setStyleSheet(BUTTON_STYLE_STOPPED)

    def UpdateUiSentinelHotkey(self, vkList: List[int]) -> None:
        """
        Update UI with sentinel hotkey information.
        
        Args:
            vkList: List of virtual key codes
        """
        self.SentinalHotkeyEdit.setText(", ".join(map(KeyNameFromVk, vkList)))

    def UpdateUiEventMatchScore(self, eventTuple: Tuple[int, float]) -> None:
        """
        Update UI with event match score.
        
        Args:
            eventTuple: Tuple containing (index, score)
        """
        index, score = eventTuple
        if self.EventListWidget.currentRow() != index:
            return
        
        self.ThresholdMatchScoreLabel.setText(f"{score:.3f}")

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
    app = QApplication(sys.argv)
    
    # MVVM Initialization
    vm = DashboardViewModel()
    view = DashboardView(vm)
    view.show()
    
    sys.exit(app.exec())