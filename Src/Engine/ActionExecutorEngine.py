from typing import List
from Src.Models import EventItem

class ActionExecutorEngine:
    """Pure logic for executing actions based on activations."""
    def loop(self, windowHandle: int, events: List[EventItem]) -> None:
        for event in events:
            # Event.Trigger handles its own enabled check.
            event.Trigger(windowHandle)