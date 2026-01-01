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

    def SaveState(self, file_path: str, *, events: List[EventItem], flow_hotkey: List[int]) -> None:
        data_to_save: Dict[str, Any] = {
            "events": events,
            "settings": flow_hotkey,
            "version": self.VERSION,
        }

        with open(file_path, "wb") as file:
            pickle.dump(data_to_save, file)

    def LoadState(self, file_path: str) -> Optional[tuple[List[EventItem], List[int], str]]:
        if not os.path.exists(file_path):
            return None

        with open(file_path, "rb") as file:
            data = pickle.load(file)

        loaded_events: List[EventItem] = []
        loaded_hotkey: List[int] = []
        loaded_version: str = self.VERSION

        if isinstance(data, dict):
            data_dict: Dict[str, Any] = cast(Dict[str, Any], data)
            loaded_events = cast(List[EventItem], data_dict.get("events", []))
            loaded_hotkey = cast(List[int], data_dict.get("settings", []))
            loaded_version = cast(str, data_dict.get("version", self.VERSION))
            return loaded_events, loaded_hotkey, loaded_version

        return None
