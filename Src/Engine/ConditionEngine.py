from uuid import UUID
import numpy as np
from dataclasses import dataclass, field
from typing import (
    cast, List, Optional, Any, Dict
)

from Src.Helper import (
    CropImage, MatchTemplate,
    EstimateProgressBarPercentage
)
from Src.Models import (
    ActivationType, 
    EventItem
)

@dataclass
class ConditionEngineState:
    MatchScore: float = 0.0
    PercentFilled: float = 0.0

@dataclass
class ConditionEngineContext:
    eventStates: Dict[UUID, ConditionEngineState] = field(
        default_factory=lambda: cast(Dict[UUID, ConditionEngineState], {})
    )

@dataclass
class ConditionEngineResult:
    matchUpdates: List[object]
    matchScores: Dict[UUID, float]
    percentFilleds: Dict[UUID, float]




# =============================================================================
# Condition Engine
# =============================================================================
class ConditionEngine:
    def Loop(
        self,
        events: List[EventItem],
        localImage: Optional[np.ndarray[Any, Any]],
        context: ConditionEngineContext
    ) -> tuple[ConditionEngineResult, ConditionEngineContext]:
        matchUpdates: List[object] = []
        matchScores: Dict[UUID, float] = {}
        percentFilleds: Dict[UUID, float] = {}
        
        for index, event in enumerate(events):
            if not event.IsEnabled:
                continue

            # Ensure state exists for this event
            if event.Uuid not in context.eventStates:
                context.eventStates[event.Uuid] = ConditionEngineState()
            state = context.eventStates[event.Uuid]

            if event.SelectedActivationType == ActivationType.Hotkey:
                pass

            elif event.SelectedActivationType == ActivationType.Loop:
                pass

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
                matchScores[event.Uuid] = state.MatchScore

            elif event.SelectedActivationType == ActivationType.ProgressBar:
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
                percentFilleds[event.Uuid] = state.PercentFilled


        return ConditionEngineResult(matchUpdates, matchScores, percentFilleds), context