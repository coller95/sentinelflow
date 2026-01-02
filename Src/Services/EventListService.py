from __future__ import annotations

from Src.Models import ActionItem, EventItem


class EventListService:
    def CreateDefaultEvent(self) -> EventItem:
        new_action = ActionItem()
        return EventItem(name="New Event", action=new_action)
