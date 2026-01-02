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
    ConditionItem,
    ConditionType
)

@dataclass
class ConditionEngineState:
    CropImage: Optional[np.ndarray[Any, Any]] = None
    MatchScore: float = 0.0
    PercentFilled: float = 0.0

@dataclass
class ConditionEngineContext:
    States: Dict[UUID, ConditionEngineState] = field(
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
        conditions: List[ConditionItem],
        localImage: Optional[np.ndarray[Any, Any]],
        context: ConditionEngineContext
    ) -> tuple[ConditionEngineResult, ConditionEngineContext]:
        matchUpdates: List[object] = []
        matchScores: Dict[UUID, float] = {}
        percentFilleds: Dict[UUID, float] = {}
        
        for condition in conditions:
            # Ensure state exists for this event
            if condition.Uuid not in context.States:
                context.States[condition.Uuid] = ConditionEngineState()
            state = context.States[condition.Uuid]

            if condition.SelectedConditionType == ConditionType.ImageMatchRoi:
                if localImage is None or condition.TemplateImage is None:
                    continue

                state.CropImage = CropImage(localImage, (
                    condition.Roi.XNormalized, 
                    condition.Roi.YNormalized, 
                    condition.Roi.WidthNormalized, 
                    condition.Roi.HeightNormalized
                ))

                state.MatchScore = MatchTemplate(state.CropImage, condition.TemplateImage)
                matchUpdates.append((condition.Uuid, state.MatchScore, state.CropImage))
                matchScores[condition.Uuid] = state.MatchScore

            elif condition.SelectedConditionType == ConditionType.ProgressBar:
                if localImage is None:
                    continue

                state.CropImage = CropImage(localImage, (
                    condition.Roi.XNormalized, 
                    condition.Roi.YNormalized, 
                    condition.Roi.WidthNormalized, 
                    condition.Roi.HeightNormalized
                ))

                state.PercentFilled = EstimateProgressBarPercentage(state.CropImage)
                matchUpdates.append((condition.Uuid, state.PercentFilled, state.CropImage))
                percentFilleds[condition.Uuid] = state.PercentFilled


        return ConditionEngineResult(matchUpdates, matchScores, percentFilleds), context