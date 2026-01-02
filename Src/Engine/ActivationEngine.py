import time
from uuid import UUID
import numpy as np
from dataclasses import dataclass
from typing import (
    List, Optional, Any, Set
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
class EngineResult:
    triggered: List[EventItem]
    disabled: List[EventItem]
    matchUpdates: List[object]
    triggeredEventUuids: Set[UUID]


class ActivationEngine:
    def loop(self, events: List[EventItem], localImage: Optional[np.ndarray[Any, Any]]) -> EngineResult:
        triggered: List[EventItem] = []
        disabled: List[EventItem] = []
        matchUpdates: List[object] = []
        triggeredEventUuids: Set[UUID] = set()

        for index, event in enumerate(events):
            if not event.IsEnabled:
                continue

            if event.SelectedActivationType == ActivationType.Hotkey:
                if len(event.ActivationVirtualKeyCodes) == 0:
                    continue

                isDownNow = IsHotkeyActive(event.ActivationVirtualKeyCodes)
                if event.IsCurrentlyHeld and not isDownNow:
                    triggered.append(event)
                    triggeredEventUuids.add(event.Uuid)
                event.IsCurrentlyHeld = isDownNow

            elif event.SelectedActivationType == ActivationType.Loop:
                if event.LoopCount < 0:
                    continue
                if event.LoopCount > 0 and event.LoopCounter >= event.LoopCount:
                    event.IsEnabled = False
                    event.ResetTransientState()
                    disabled.append(event)
                    continue

                currentTimeMs = int(time.time() * 1000)
                if currentTimeMs - event.TimeOfLastTriggerMilliseconds < event.IntervalMilliseconds:
                    continue

                event.LoopCounter += 1
                event.TimeOfLastTriggerMilliseconds = currentTimeMs
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

                event.MatchScore = MatchTemplate(localImageRoi, event.TemplateImage)
                matchUpdates.append(event.MatchScore)

                if event.TriggerOnThresholdExceed:
                    isConditionMet = event.MatchScore >= event.Threshold
                else:
                    isConditionMet = event.MatchScore < event.Threshold

                currentTimeMs = int(time.time() * 1000)
                timeSinceLastTrigger = currentTimeMs - event.TimeOfLastTriggerMilliseconds

                isRisingEdge = isConditionMet and not event.IsCurrentlyHeld
                isRetrigger = isConditionMet and (timeSinceLastTrigger > event.RetriggerTimeMilliseconds)

                if isRisingEdge or isRetrigger:
                    triggered.append(event)
                    triggeredEventUuids.add(event.Uuid)
                    event.TimeOfLastTriggerMilliseconds = currentTimeMs

                event.IsCurrentlyHeld = isConditionMet

            elif event.SelectedActivationType in (ActivationType.ProgressBar, ActivationType.ProgressBar):
                if localImage is None:
                    continue

                localImageRoi = CropImage(localImage, (
                    event.Roi.XNormalized, 
                    event.Roi.YNormalized, 
                    event.Roi.WidthNormalized, 
                    event.Roi.HeightNormalized
                ))

                event.PercentFilled = EstimateProgressBarPercentage(localImageRoi)
                matchUpdates.append((index, event.PercentFilled))

                if event.TriggerOnThresholdExceed:
                    isConditionMet = event.PercentFilled >= event.Threshold
                else:
                    isConditionMet = event.PercentFilled < event.Threshold

                currentTimeMs = int(time.time() * 1000)
                timeSinceLastTrigger = currentTimeMs - event.TimeOfLastTriggerMilliseconds

                isRisingEdge = isConditionMet and not event.IsCurrentlyHeld
                isRetrigger = isConditionMet and (timeSinceLastTrigger > event.RetriggerTimeMilliseconds)

                if isRisingEdge or isRetrigger:
                    triggered.append(event)
                    triggeredEventUuids.add(event.Uuid)
                    event.TimeOfLastTriggerMilliseconds = currentTimeMs

                event.IsCurrentlyHeld = isConditionMet

        return EngineResult(triggered=triggered, disabled=disabled, matchUpdates=matchUpdates, triggeredEventUuids=triggeredEventUuids)