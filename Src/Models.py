import time
import numpy as np
from enum import Enum, auto
from typing import (
    List, Optional, Any
)

# Local imports
from Src.Helper import (
    SendKeystrokeToWindow, SendMouseClickToWindow
)

# =============================================================================
# ENUMERATIONS
# =============================================================================
class ActivationType(Enum):
    """Types of event activation mechanisms."""
    NotSet = auto()
    Hotkey = auto()
    Loop = auto()
    ImageMatchRoi = auto()
    ProgressBar = auto()

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
        roi: Optional[RectangleRegion] = None,  # FIX: avoid shared mutable default
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
        self._roi: RectangleRegion = roi if roi is not None else RectangleRegion(0.0, 0.0, 1.0, 1.0)
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

    def ResetTransientState(self) -> None:
        """Reset counters/edge-detection state so enabling/type changes behave predictably."""
        self._isCurrentlyHeld = False
        self._loopCounter = 0
        self._timeOfLastTriggerMilliseconds = 0.0
        self._matchScore = 0.0
        self._percentFilled = 0.0

    def Trigger(self, windowHandle: int) -> None:
        """
        Trigger the event's assigned action on the specified window.
        
        Args:
            windowHandle: Handle to the target window
        """
        if self._enabled and self._assignedAction:
            self._assignedAction.Execute(windowHandle)
