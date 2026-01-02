from __future__ import annotations

from typing import List, Optional

from Src.Models import ActionItem, EventItem


class EventListService:
    def CreateDefaultEvent(self) -> EventItem:
        new_action = ActionItem()
        return EventItem(name="New Event", action=new_action)

    def RemoveSelectedEvent(self, events: List[EventItem], selected: Optional[EventItem]) -> Optional[int]:
        if selected is None:
            return None
        try:
            index = events.index(selected)
        except ValueError:
            return None
        if 0 <= index < len(events):
            events.pop(index)
            return index
        return None
