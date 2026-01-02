from __future__ import annotations

import threading
from typing import List, Optional

from Src.Models import EventItem


class EventStoreService:
    """Thread-safe store for EventItem list.

    Why this exists:
    - UI thread mutates events (add/remove/edit)
    - Sentinel polling thread reads events frequently

    Refactor-only goal:
    - Preserve current behavior while avoiding concurrent iteration over a mutating list.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: List[EventItem] = []

    def GetSnapshot(self) -> List[EventItem]:
        """Return a stable snapshot copy for background processing."""
        with self._lock:
            return list(self._events)

    def GetAll(self) -> List[EventItem]:
        """Return a copy for persistence/export."""
        return self.GetSnapshot()

    def Add(self, event: EventItem) -> None:
        with self._lock:
            self._events.append(event)

    def Clear(self) -> None:
        with self._lock:
            self._events.clear()

    def RemoveSelected(self, selected: Optional[EventItem]) -> Optional[int]:
        if selected is None:
            return None
        with self._lock:
            try:
                index = self._events.index(selected)
            except ValueError:
                return None
            self._events.pop(index)
            return index

    def MoveByIndex(self, fromIndex: int, toIndex: int) -> None:
        with self._lock:
            if fromIndex < 0 or toIndex < 0:
                return
            if fromIndex >= len(self._events) or toIndex >= len(self._events):
                return
            if fromIndex == toIndex:
                return

            event = self._events.pop(fromIndex)
            self._events.insert(toIndex, event)
