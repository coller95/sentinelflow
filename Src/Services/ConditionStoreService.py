from __future__ import annotations

import threading
from typing import Dict, List, Optional
from uuid import UUID

from Src.Models import ConditionItem, EventItem


class ConditionStoreService:
    """Thread-safe store for reusable ConditionItem objects.

    The store is treated as the *library* of shared conditions the UI can pick from.
    We keep it consistent with the current event list by rebuilding/deduping based
    on the conditions referenced by events.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._conditionsById: Dict[UUID, ConditionItem] = {}
        self._orderedIds: List[UUID] = []
        self.EnsureDummyCondition()

    def EnsureDummyCondition(self) -> None:
        """Ensure the library always has at least one condition."""
        with self._lock:
            if len(self._orderedIds) > 0:
                return
            dummy = ConditionItem()
            dummy.Name = "Dummy Condition"
            self._conditionsById[dummy.Uuid] = dummy
            self._orderedIds.append(dummy.Uuid)

    def Clear(self) -> None:
        with self._lock:
            self._conditionsById.clear()
            self._orderedIds.clear()
        self.EnsureDummyCondition()

    def ReplaceAll(self, conditions: List[ConditionItem]) -> None:
        """Replace the entire library with the provided ordered list.

        Used for loading from disk: preserves file order, dedupes by UUID, and
        only injects a Dummy Condition if the loaded list is empty.
        """
        with self._lock:
            self._conditionsById.clear()
            self._orderedIds.clear()

            for condition in conditions:
                if not isinstance(condition, ConditionItem):
                    continue
                cid = condition.Uuid
                if cid in self._conditionsById:
                    continue
                self._conditionsById[cid] = condition
                self._orderedIds.append(cid)

            if len(self._orderedIds) == 0:
                dummy = ConditionItem()
                dummy.Name = "Dummy Condition"
                self._conditionsById[dummy.Uuid] = dummy
                self._orderedIds.append(dummy.Uuid)

    def Add(self, condition: ConditionItem) -> None:
        with self._lock:
            if condition.Uuid in self._conditionsById:
                # Keep first insertion order.
                self._conditionsById[condition.Uuid] = condition
                return
            self._conditionsById[condition.Uuid] = condition
            self._orderedIds.append(condition.Uuid)

    def RemoveByUuid(self, conditionId: UUID) -> None:
        with self._lock:
            if conditionId in self._conditionsById:
                self._conditionsById.pop(conditionId, None)
            self._orderedIds = [cid for cid in self._orderedIds if cid != conditionId]

    def GetByUuid(self, conditionId: UUID) -> Optional[ConditionItem]:
        with self._lock:
            return self._conditionsById.get(conditionId)

    def GetSnapshot(self) -> List[ConditionItem]:
        with self._lock:
            return [self._conditionsById[cid] for cid in self._orderedIds if cid in self._conditionsById]

    def MoveByIndex(self, fromIndex: int, toIndex: int) -> None:
        with self._lock:
            if fromIndex < 0 or fromIndex >= len(self._orderedIds):
                return
            if toIndex < 0 or toIndex >= len(self._orderedIds):
                return
            if fromIndex == toIndex:
                return
            cid = self._orderedIds.pop(fromIndex)
            self._orderedIds.insert(toIndex, cid)

    def RebuildFromEvents(self, events: List[EventItem]) -> None:
        """Rebuild the library to exactly the set of conditions referenced by events."""
        with self._lock:
            newById: Dict[UUID, ConditionItem] = {}
            newOrdered: List[UUID] = []
            for event in events:
                condition = event.Condition
                cid = condition.Uuid
                if cid in newById:
                    continue
                newById[cid] = condition
                newOrdered.append(cid)
            self._conditionsById = newById
            self._orderedIds = newOrdered
