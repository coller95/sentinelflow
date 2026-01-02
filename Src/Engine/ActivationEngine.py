import time
from uuid import UUID
import numpy as np
from dataclasses import dataclass, field
from typing import (
    cast, List, Optional, Any, Set, Dict
)
from Src.Helper import (
    CropImage, MatchTemplate, IsHotkeyActive,
    EstimateProgressBarPercentage
)

from Src.Models import (
    ActivationType, 
    EventItem
)


@dataclass
class EventActivationState:
    IsCurrentlyHeld: bool = False
    LoopCounter: int = 0
    LastTriggerTimeMs: int = 0
    MatchScore: float = 0.0
    PercentFilled: float = 0.0

@dataclass
class ActivationEngineContext:
    eventStates: Dict[UUID, EventActivationState] = field(
        default_factory=lambda: cast(Dict[UUID, EventActivationState], {})
    )

@dataclass
class ActivationEngineResult:
    triggered: List[EventItem]
    disabled: List[EventItem]
    matchUpdates: List[object]
    triggeredEventUuids: Set[UUID]


class ActivationEngine:
    def loop(self, events: List[EventItem], localImage: Optional[np.ndarray[Any, Any]], context: ActivationEngineContext) -> tuple[ActivationEngineResult, ActivationEngineContext]:
        triggered: List[EventItem] = []
        disabled: List[EventItem] = []
        matchUpdates: List[object] = []
        triggeredEventUuids: Set[UUID] = set()

        for index, event in enumerate(events):
            if not event.IsEnabled:
                continue

            # Ensure state exists for this event
            if event.Uuid not in context.eventStates:
                context.eventStates[event.Uuid] = EventActivationState()
            state = context.eventStates[event.Uuid]

            if event.SelectedActivationType == ActivationType.Hotkey:
                if len(event.ActivationVirtualKeyCodes) == 0:
                    continue

                isDownNow = IsHotkeyActive(event.ActivationVirtualKeyCodes)
                if state.IsCurrentlyHeld and not isDownNow:
                    triggered.append(event)
                    triggeredEventUuids.add(event.Uuid)
                state.IsCurrentlyHeld = isDownNow

            elif event.SelectedActivationType == ActivationType.Loop:
                if event.LoopCount < 0:
                    continue
                if event.LoopCount > 0 and state.LoopCounter >= event.LoopCount:
                    event.IsEnabled = False
                    event.ResetTransientState()
                    disabled.append(event)
                    continue

                currentTimeMs = int(time.time() * 1000)
                if currentTimeMs - state.LastTriggerTimeMs < event.IntervalMilliseconds:
                    continue

                state.LoopCounter += 1
                state.LastTriggerTimeMs = currentTimeMs
                triggered.append(event)
                triggeredEventUuids.add(event.Uuid)

            elif event.SelectedActivationType == ActivationType.ImageMatchRoi:
                if localImage is None or event.TemplateImage is None:
                    continue

                localImageRoi = CropImage(localImage, (
                    event.Roi.XNormalized, 
                    event.Roi.YNormalized, 
                    event.Roi.WidthNormalized, 
                    event.Roi.HeightNormalized
                ))

                state.MatchScore = MatchTemplate(localImageRoi, event.TemplateImage)
                matchUpdates.append(state.MatchScore)

                if event.TriggerOnThresholdExceed:
                    isConditionMet = state.MatchScore >= event.Threshold
                else:
                    isConditionMet = state.MatchScore < event.Threshold

                currentTimeMs = int(time.time() * 1000)
                timeSinceLastTrigger = currentTimeMs - state.LastTriggerTimeMs

                isRisingEdge = isConditionMet and not state.IsCurrentlyHeld
                isRetrigger = isConditionMet and (timeSinceLastTrigger > event.RetriggerTimeMilliseconds)

                if isRisingEdge or isRetrigger:
                    triggered.append(event)
                    triggeredEventUuids.add(event.Uuid)
                    state.LastTriggerTimeMs = currentTimeMs

                state.IsCurrentlyHeld = isConditionMet

            elif event.SelectedActivationType in (ActivationType.ProgressBar, ActivationType.ProgressBar):
                if localImage is None:
                    continue

                localImageRoi = CropImage(localImage, (
                    event.Roi.XNormalized, 
                    event.Roi.YNormalized, 
                    event.Roi.WidthNormalized, 
                    event.Roi.HeightNormalized
                ))

                state.PercentFilled = EstimateProgressBarPercentage(localImageRoi)
                matchUpdates.append((index, state.PercentFilled))

                if event.TriggerOnThresholdExceed:
                    isConditionMet = state.PercentFilled >= event.Threshold
                else:
                    isConditionMet = state.PercentFilled < event.Threshold

                currentTimeMs = int(time.time() * 1000)
                timeSinceLastTrigger = currentTimeMs - state.LastTriggerTimeMs

                isRisingEdge = isConditionMet and not state.IsCurrentlyHeld
                isRetrigger = isConditionMet and (timeSinceLastTrigger > event.RetriggerTimeMilliseconds)

                if isRisingEdge or isRetrigger:
                    triggered.append(event)
                    triggeredEventUuids.add(event.Uuid)
                    state.LastTriggerTimeMs = currentTimeMs

                state.IsCurrentlyHeld = isConditionMet

        return ActivationEngineResult(
            triggered=triggered,
            disabled=disabled,
            matchUpdates=matchUpdates,
            triggeredEventUuids=triggeredEventUuids
        ), context