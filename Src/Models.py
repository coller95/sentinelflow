import numpy as np
from enum import Enum, auto
from typing import List, Optional, Any

class ActivationType(Enum):
    NotSet = auto()
    Hotkey = auto()
    Loop = auto()
    ImageMatchRoi = auto()
    ProgressBar = auto()


class InputType(Enum):
    Mouse = auto()
    Keyboard = auto()
    Delay = auto()

class RectangleRegion:
    def __init__(self, xNormalized: float = 0.0, yNormalized: float = 0.0, 
                 widthNormalized: float = 1.0, heightNormalized: float = 1.0) -> None:
        self._xNormalized: float = xNormalized
        self._yNormalized: float = yNormalized
        self._widthNormalized: float = widthNormalized
        self._heightNormalized: float = heightNormalized


    @property
    def XNormalized(self) -> float:
        return self._xNormalized
    
    @XNormalized.setter
    def XNormalized(self, value: float) -> None:
        self._xNormalized = value


    @property
    def YNormalized(self) -> float:
        return self._yNormalized
    
    @YNormalized.setter
    def YNormalized(self, value: float) -> None:
        self._yNormalized = value


    @property
    def WidthNormalized(self) -> float:
        return self._widthNormalized
    
    @WidthNormalized.setter
    def WidthNormalized(self, value: float) -> None:
        self._widthNormalized = value


    @property
    def HeightNormalized(self) -> float:
        return self._heightNormalized
    
    @HeightNormalized.setter
    def HeightNormalized(self, value: float) -> None:
        self._heightNormalized = value



class MacroStep:
    def __init__(self, inputType: InputType, value: Any = None, description: str = "") -> None:
        self._inputType: InputType = inputType
        self._value: Any = value
        self._description: str = description


    @property
    def Description(self) -> str:
        return self._description
    
    @Description.setter
    def Description(self, value: str) -> None:
        self._description = value


    @property
    def InputType(self) -> InputType:
        return self._inputType

    @property
    def Value(self) -> Any:
        return self._value



class ActionItem:
    def __init__(self) -> None:
        self._macroSteps: List[MacroStep] = []


    @property
    def MacroSteps(self) -> List[MacroStep]:
        return self._macroSteps

    def AddStep(self, macroStep: MacroStep) -> None:
        self._macroSteps.append(macroStep)

    def RemoveStep(self, index: int) -> None:
        if 0 <= index < len(self._macroSteps):
            self._macroSteps.pop(index)



class EventItem:
    def __init__(
        self,
        name: str,
        action: ActionItem,
        enabled: bool = False,
        activationType: ActivationType = ActivationType.NotSet,
        loopCount: int = 0,
        intervalMilliseconds: int = 1000,
        roi: Optional[RectangleRegion] = None,
        threshold: float = 0.99,
        retriggerTimeMilliseconds: float = 2000
    ) -> None:
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
        return self._name
    
    @Name.setter
    def Name(self, value: str) -> None:
        self._name = value


    @property
    def IsEnabled(self) -> bool:
        return self._enabled
    
    @IsEnabled.setter
    def IsEnabled(self, value: bool) -> None:
        self._enabled = value


    @property
    def SelectedActivationType(self) -> ActivationType:
        return self._selectedActivationType
    
    @SelectedActivationType.setter
    def SelectedActivationType(self, value: ActivationType) -> None:
        self._selectedActivationType = value


    @property
    def ActivationVirtualKeyCodes(self) -> List[int]:
        return self._activationVirtualKeyCodes
    
    @ActivationVirtualKeyCodes.setter
    def ActivationVirtualKeyCodes(self, value: List[int]) -> None:
        self._activationVirtualKeyCodes = value


    @property
    def IsCurrentlyHeld(self) -> bool:
        return self._isCurrentlyHeld
    
    @IsCurrentlyHeld.setter
    def IsCurrentlyHeld(self, value: bool) -> None:
        self._isCurrentlyHeld = value


    @property
    def LoopCount(self) -> int:
        return self._loopCount
    
    @LoopCount.setter
    def LoopCount(self, value: int) -> None:
        self._loopCount = value


    @property
    def LoopCounter(self) -> int:
        return self._loopCounter
    
    @LoopCounter.setter
    def LoopCounter(self, value: int) -> None:
        self._loopCounter = value


    @property
    def IntervalMilliseconds(self) -> int:
        return self._intervalMilliseconds
    
    @IntervalMilliseconds.setter
    def IntervalMilliseconds(self, value: int) -> None:
        self._intervalMilliseconds = value


    @property
    def TimeOfLastTriggerMilliseconds(self) -> float:
        return self._timeOfLastTriggerMilliseconds
    
    @TimeOfLastTriggerMilliseconds.setter
    def TimeOfLastTriggerMilliseconds(self, value: float) -> None:
        self._timeOfLastTriggerMilliseconds = value


    @property
    def Roi(self) -> RectangleRegion:
        return self._roi
    
    @Roi.setter
    def Roi(self, value: RectangleRegion) -> None:
        self._roi = value


    @property
    def TemplateImage(self) -> Optional[np.ndarray[Any, Any]]:
        return self._templateImage
    
    @TemplateImage.setter
    def TemplateImage(self, value: Optional[np.ndarray[Any, Any]]) -> None:
        self._templateImage = value


    @property
    def Threshold(self) -> float:
        return self._threshold
    
    @Threshold.setter
    def Threshold(self, value: float) -> None:
        self._threshold = value


    @property
    def TriggerOnThresholdExceed(self) -> bool:
        return self._triggerOnThresholdExceed
    
    @TriggerOnThresholdExceed.setter
    def TriggerOnThresholdExceed(self, value: bool) -> None:
        self._triggerOnThresholdExceed = value


    @property
    def RetriggerTimeMilliseconds(self) -> float:
        return self._retriggerTimeMilliseconds
    
    @RetriggerTimeMilliseconds.setter
    def RetriggerTimeMilliseconds(self, value: float) -> None:
        self._retriggerTimeMilliseconds = value


    @property
    def MatchScore(self) -> float:
        return self._matchScore
    
    @MatchScore.setter
    def MatchScore(self, value: float) -> None:
        self._matchScore = value


    @property
    def PercentFilled(self) -> float:
        return self._percentFilled
    
    @PercentFilled.setter
    def PercentFilled(self, value: float) -> None:
        self._percentFilled = value


    @property
    def AssignedAction(self) -> ActionItem:
        return self._assignedAction
    
    @AssignedAction.setter
    def AssignedAction(self, value: ActionItem) -> None:
        self._assignedAction = value

    def ResetTransientState(self) -> None:
        self._isCurrentlyHeld = False
        self._loopCounter = 0
        self._timeOfLastTriggerMilliseconds = 0.0
        self._matchScore = 0.0
        self._percentFilled = 0.0

