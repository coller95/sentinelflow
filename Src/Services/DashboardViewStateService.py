from __future__ import annotations

from typing import Optional

from Src.Models import EventItem


class DashboardViewStateService:
    def __init__(self) -> None:
        self.SelectedEventItem: Optional[EventItem] = None
        self.CaptureMousePositionNormalized: Optional[tuple[float, float]] = None
