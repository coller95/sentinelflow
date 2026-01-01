from __future__ import annotations

from typing import Optional

from Src.Models import EventItem


class DashboardViewStateService:
    """Holds mutable UI/ViewModel state (selection, captured positions).

    Refactor-only goal:
    - Centralize transient UI state so DashboardViewModel can focus on orchestration + signals.
    """

    def __init__(self) -> None:
        self.SelectedEventItem: Optional[EventItem] = None
        self.CaptureMousePositionNormalized: Optional[tuple[float, float]] = None
