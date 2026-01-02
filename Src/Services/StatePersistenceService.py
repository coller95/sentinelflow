from __future__ import annotations

import os
import pickle
from typing import Any, Dict, List, Optional, cast

from Src.Models import EventItem


class StatePersistenceService:
    """Persists and restores SentinelFlow state.

    Refactor-only goal:
    - Preserve the exact save format currently used by DashboardViewModel.
    - Keep load logic tolerant to the current "dict" format.
    """

    VERSION = "1.0.0"

    def SaveState(self, filePath: str, *, events: List[EventItem], flowHotkey: List[int]) -> None:
        dataToSave: Dict[str, Any] = {
            "events": events,
            "settings": flowHotkey,
            "version": self.VERSION,
        }

        with open(filePath, "wb") as file:
            pickle.dump(dataToSave, file)

    def LoadState(self, filePath: str) -> Optional[tuple[List[EventItem], List[int], str]]:
        if not os.path.exists(filePath):
            return None

        with open(filePath, "rb") as file:
            data = pickle.load(file)

        loadedEvents: List[EventItem] = []
        loadedHotkey: List[int] = []
        loadedVersion: str = self.VERSION

        if isinstance(data, dict):
            dataDict: Dict[str, Any] = cast(Dict[str, Any], data)
            loadedEvents = cast(List[EventItem], dataDict.get("events", []))
            loadedHotkey = cast(List[int], dataDict.get("settings", []))
            loadedVersion = cast(str, dataDict.get("version", self.VERSION))
            return loadedEvents, loadedHotkey, loadedVersion

        return None
