import time

from uuid import UUID

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, cast

from Src.Helper import SendKeyChordToWindow, SendKeystrokeToWindow, SendMouseClickToWindow
from Src.Models import ActionItem, EventItem, InputType, MacroStep



# =============================================================================
# Context and State Classes
# =============================================================================
@dataclass
class EventExecutionState:
    currentStepIndex: int = 0
    delayStartTime: Optional[float] = None  # Unix timestamp when delay started

@dataclass
class ActionExecutionContext:
    eventStates: Dict[UUID, EventExecutionState] = field(
        default_factory=lambda: cast(Dict[UUID, EventExecutionState], {})
    )
    

# =============================================================================
# Step Execution Strategies
# =============================================================================
class StepExecutionStrategy:
    def execute(self, windowHandle: int, step: MacroStep, state: EventExecutionState) -> bool:
        raise NotImplementedError

class KeyboardStepStrategy(StepExecutionStrategy):
    def __init__(self, sendKeystrokeFunc : Any):
        self._sendKeystroke = sendKeystrokeFunc
    def execute(self, windowHandle: int, step: MacroStep, state: EventExecutionState) -> bool:
        self._sendKeystroke(windowHandle, step.Value)
        return True

class MouseStepStrategy(StepExecutionStrategy):
    def execute(self, windowHandle: int, step: MacroStep, state: EventExecutionState) -> bool:
        value = step.Value
        SendMouseClickToWindow(windowHandle, float(value[0]), float(value[1]))
        return True

class DelayStepStrategy(StepExecutionStrategy):
    def execute(self, windowHandle: int, step: MacroStep, state: EventExecutionState) -> bool:
        delayMs = float(step.Value)
        now = time.time()
        if state.delayStartTime is None:
            state.delayStartTime = now
            return False
        elapsed = (now - state.delayStartTime) * 1000.0
        if elapsed >= delayMs:
            return True
        return False


# =============================================================================
# Action Executor Engine
# =============================================================================
class ActionExecutorEngine:
    def __init__(self):
        self.stepStrategies : dict[InputType, StepExecutionStrategy] = {
            InputType.Keyboard: KeyboardStepStrategy(self.sendKeystroke),
            InputType.Mouse: MouseStepStrategy(),
            InputType.Delay: DelayStepStrategy(),
        }
        
    def executeAction(self, windowHandle: int, action: Optional[ActionItem], state: EventExecutionState) -> None:
        if not action:
            return
        steps = action.MacroSteps
        # Only execute the current step
        if 0 <= state.currentStepIndex < len(steps):
            step = steps[state.currentStepIndex]
            stepCompleted = self.executeStep(windowHandle, step, state)
            if stepCompleted:
                state.currentStepIndex += 1
                state.delayStartTime = None
            # If not completed (e.g., delay not finished), keep index and delay time

    def executeStep(self, windowHandle: int, step: MacroStep, state: EventExecutionState) -> bool:
        strategy = self.stepStrategies.get(step.InputType)
        if strategy is not None:
            return strategy.execute(windowHandle, step, state)
        return True

    def sendKeystroke(self, hwnd: int, value: Any) -> None:
        if isinstance(value, (list, tuple)):
            seq = cast(list[int] | tuple[int, ...], value)
            keys = [int(vk) for vk in seq]
            SendKeyChordToWindow(hwnd, keys)
            return
        SendKeystrokeToWindow(hwnd, int(value))

    def Loop(
        self,
        windowHandle: int,
        events: List[EventItem],
        triggeredEventUuids: Set[UUID],
        context: ActionExecutionContext
    ) -> ActionExecutionContext:
        toRemove : list[UUID] = []
        for event in events:
            if not event.IsEnabled:
                continue
            
            state = context.eventStates.get(event.Uuid)
            # if activated, check context and add state if not present
            if event.Uuid in triggeredEventUuids:
                if state is None:
                    state = EventExecutionState()
                    context.eventStates[event.Uuid] = state

            # Execute when uuid found in context
            if state is not None:
                self.executeAction(windowHandle, event.AssignedAction, state)

                # After execution, check if done to remove from context
                if state.currentStepIndex >= len(event.AssignedAction.MacroSteps):
                    toRemove.append(event.Uuid)

        # Remove completed or deactivated events
        for uuid in toRemove:
            context.eventStates.pop(uuid, None)
        return context