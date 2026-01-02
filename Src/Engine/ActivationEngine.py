import time
from uuid import UUID
from dataclasses import dataclass, field
from typing import (
    cast, List, Set, Dict
)
from Src.Helper import IsHotkeyActive

from Src.Models import (
    ActivationType, 
    EventItem
)

from Src.Engine.ConditionEngine import ConditionEngineResult

# =============================================================================
# Context and State Classes
# =============================================================================
@dataclass
class EventActivationState:
    IsCurrentlyHeld: bool = False
    LoopCounter: int = 0
    LastTriggerTimeMs: int = 0

@dataclass
class ActivationEngineContext:
    eventStates: Dict[UUID, EventActivationState] = field(
        default_factory=lambda: cast(Dict[UUID, EventActivationState], {})
    )

@dataclass
class ActivationEngineResult:
    triggered: List[EventItem]
    disabled: List[EventItem]
    triggeredEventUuids: Set[UUID]

# =============================================================================
# Activation Engine
# =============================================================================
class ActivationEngine:
    def Loop(
        self,
        events: List[EventItem],
        conditionEngineResult: ConditionEngineResult,
        context: ActivationEngineContext
    ) -> tuple[ActivationEngineResult, ActivationEngineContext]:
        triggered: List[EventItem] = []
        disabled: List[EventItem] = []
        triggeredEventUuids: Set[UUID] = set()

        activeEventUuids: Set[UUID] = {e.Uuid for e in events if e.IsEnabled}

        for event in events:
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
                    context.eventStates.pop(event.Uuid, None)
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
                matchScore = conditionEngineResult.matchScores.get(event.Condition.Uuid, None) # please be aware that this is condition.Uuid, not event.Uuid
                if matchScore is None:
                    continue # Skip if no data


                if event.TriggerOnThresholdExceed:
                    isConditionMet = matchScore >= event.Threshold
                else:
                    isConditionMet = matchScore < event.Threshold

                currentTimeMs = int(time.time() * 1000)
                timeSinceLastTrigger = currentTimeMs - state.LastTriggerTimeMs

                isRisingEdge = isConditionMet and not state.IsCurrentlyHeld
                isRetrigger = isConditionMet and (timeSinceLastTrigger > event.RetriggerTimeMilliseconds)

                if isRisingEdge or isRetrigger:
                    triggered.append(event)
                    triggeredEventUuids.add(event.Uuid)
                    state.LastTriggerTimeMs = currentTimeMs

                state.IsCurrentlyHeld = isConditionMet

            elif event.SelectedActivationType == ActivationType.ProgressBar:
                percentFilled = conditionEngineResult.percentFilleds.get(event.Condition.Uuid, None) # please be aware that this is condition.Uuid, not event.Uuid
                if percentFilled is None:
                    continue # Skip if no data

                if event.TriggerOnThresholdExceed:
                    isConditionMet = percentFilled >= event.Threshold
                else:
                    isConditionMet = percentFilled < event.Threshold

                currentTimeMs = int(time.time() * 1000)
                timeSinceLastTrigger = currentTimeMs - state.LastTriggerTimeMs

                isRisingEdge = isConditionMet and not state.IsCurrentlyHeld
                isRetrigger = isConditionMet and (timeSinceLastTrigger > event.RetriggerTimeMilliseconds)

                if isRisingEdge or isRetrigger:
                    triggered.append(event)
                    triggeredEventUuids.add(event.Uuid)
                    state.LastTriggerTimeMs = currentTimeMs

                state.IsCurrentlyHeld = isConditionMet

        # Prune state for disabled/removed events.
        for eventUuid in list(context.eventStates.keys()):
            if eventUuid not in activeEventUuids:
                context.eventStates.pop(eventUuid, None)

        return ActivationEngineResult(
            triggered=triggered,
            disabled=disabled,
            triggeredEventUuids=triggeredEventUuids
        ), context