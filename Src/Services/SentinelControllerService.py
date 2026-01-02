from __future__ import annotations

from typing import Callable, List, Optional, Any

import numpy as np

from Src.Models import EventItem
from Src.Services.SentinelServices import TriggerMonitorService, LiveCaptureService


class SentinelControllerService:
    def __init__(
        self,
        *,
        get_event_items: Callable[[], List[EventItem]],
        get_window_handle: Callable[[], Optional[int]],
        poll_interval_ms: int = 50,
        capture_interval_ms: int = 200,
        on_image: Optional[Callable[[Optional[np.ndarray[Any, Any]]], None]] = None,
        on_event_detected: Optional[Callable[[EventItem], None]] = None,
        on_event_disabled: Optional[Callable[[EventItem], None]] = None,
        on_flow_state_changed: Optional[Callable[[bool], None]] = None,
        on_flow_hotkey_changed: Optional[Callable[[List[int]], None]] = None,
        on_match_score_updated: Optional[Callable[[object], None]] = None,
    ) -> None:
        self._get_event_items = get_event_items
        self._get_window_handle = get_window_handle
        self._poll_interval_ms = poll_interval_ms
        self._capture_interval_ms = capture_interval_ms
        self._on_image = on_image
        self._trigger_thread: Optional[TriggerMonitorService] = None
        self._live_thread: Optional[LiveCaptureService] = None
        self._on_event_detected = on_event_detected
        self._on_event_disabled = on_event_disabled
        self._on_flow_state_changed = on_flow_state_changed
        self._on_flow_hotkey_changed = on_flow_hotkey_changed
        self._on_match_score_updated = on_match_score_updated

    def StartSentinel(self) -> None:
        if self._trigger_thread is not None:
            return
        self._trigger_thread = TriggerMonitorService(
            get_event_items=self._get_event_items,
            get_window_handle=self._get_window_handle,
            poll_interval_ms=self._poll_interval_ms,
            on_event_detected=self._on_event_detected,
            on_event_disabled=self._on_event_disabled,
            on_flow_state_changed=self._on_flow_state_changed,
            on_flow_hotkey_changed=self._on_flow_hotkey_changed,
            on_match_score_updated=self._on_match_score_updated,
        )
        self._trigger_thread.Start()

    def StopSentinel(self) -> None:
        if self._trigger_thread is not None:
            self._trigger_thread.Stop()
            self._trigger_thread = None

    def ToggleFlowEnabled(self) -> None:
        if self._trigger_thread is not None:
            self._trigger_thread.ToggleFlowEnabled()

    def SetFlowEnabled(self, is_enabled: bool) -> None:
        if self._trigger_thread is not None:
            self._trigger_thread.SetFlowEnabled(is_enabled)

    def SetFlowHotkey(self, virtual_key_codes: List[int]) -> None:
        if self._trigger_thread is not None:
            self._trigger_thread.SetFlowHotkey(virtual_key_codes)

    def GetFlowHotkey(self) -> List[int]:
        if self._trigger_thread is None:
            return []
        return self._trigger_thread.GetFlowHotkey()

    def SetImage(self, image: Optional[np.ndarray[Any, Any]]) -> None:
        if self._trigger_thread is not None:
            self._trigger_thread.SetImage(image)

    # -------------------- Capture --------------------

    def ToggleCapture(self, active: bool, window_handle: Optional[int]) -> None:
        if active and window_handle:
            self.StopCapture()
            self._live_thread = LiveCaptureService(
                window_handle=window_handle,
                interval_ms=self._capture_interval_ms,
                on_image=self._handle_image_captured,
            )
            self._live_thread.Start()
        else:
            self.StopCapture()

    def StopCapture(self) -> None:
        if self._live_thread is not None:
            self._live_thread.Stop()
            self._live_thread = None

    def _handle_image_captured(self, image: Optional[np.ndarray[Any, Any]]) -> None:
        # Preserve the old wiring: captured image flows to UI and to trigger engine.
        if self._on_image is not None:
            self._on_image(image)
        self.SetImage(image)
