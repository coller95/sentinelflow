from __future__ import annotations

from Src.Models import ActionItem, ConditionItem, EventItem


class EventListService:
    def CreateDefaultEvent(self, condition: ConditionItem) -> EventItem:
        new_action = ActionItem()
        return EventItem(name="New Event", action=new_action, condition=condition)
