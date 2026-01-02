from __future__ import annotations

import os
import pickle
from typing import Any, Dict, List, Optional, cast

from Src.Models import ConditionItem, EventItem


class StatePersistenceService:
    """Persists and restores SentinelFlow state (strict format)."""

    VERSION = "2.0.0"

    def SaveState(
        self,
        filePath: str,
        *,
        events: List[EventItem],
        conditions: List[ConditionItem],
        flowHotkey: List[int],
    ) -> None:
        dataToSave: Dict[str, Any] = {
            "events": events,
            "conditions": conditions,
            "settings": flowHotkey,
            "version": self.VERSION,
        }

        with open(filePath, "wb") as file:
            pickle.dump(dataToSave, file)

    def LoadState(self, filePath: str) -> tuple[List[EventItem], List[int], str, List[ConditionItem]]:
        if not os.path.exists(filePath):
            raise FileNotFoundError(filePath)

        with open(filePath, "rb") as file:
            data = pickle.load(file)

        if not isinstance(data, dict):
            raise ValueError("Invalid state file format (expected dict)")

        dataDict: Dict[str, Any] = cast(Dict[str, Any], data)
        if "events" not in dataDict or "conditions" not in dataDict or "settings" not in dataDict:
            raise ValueError("Invalid state file format (missing keys)")

        loadedEvents = cast(List[EventItem], dataDict["events"])
        loadedConditions = cast(List[ConditionItem], dataDict["conditions"])
        loadedHotkey = cast(List[int], dataDict["settings"])
        loadedVersion = cast(str, dataDict.get("version", self.VERSION))
        return loadedEvents, loadedHotkey, loadedVersion, loadedConditions
