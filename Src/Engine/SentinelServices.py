import time
import threading
from typing import Callable, List, Optional, Any

import numpy as np

from Src.Helper import CaptureWindowByHwnd, IsHotkeyActive
from Src.Models import EventItem
from Src.Engine.ActivationEngine import ActivationEngine


class TriggerMonitorService:
    def __init__(
        self,
        get_event_items: Callable[[], List[EventItem]],
        poll_interval_ms: int = 50,
        on_event_triggered: Optional[Callable[[EventItem], None]] = None,
        on_event_disabled: Optional[Callable[[EventItem], None]] = None,
        on_flow_state_changed: Optional[Callable[[bool], None]] = None,
        on_flow_hotkey_changed: Optional[Callable[[List[int]], None]] = None,
        on_match_score_updated: Optional[Callable[[object], None]] = None,
    ) -> None:
        self._get_event_items = get_event_items
        self._poll_interval_ms = poll_interval_ms

        self._on_event_triggered = on_event_triggered
        self._on_event_disabled = on_event_disabled
        self._on_flow_state_changed = on_flow_state_changed
        self._on_flow_hotkey_changed = on_flow_hotkey_changed
        self._on_match_score_updated = on_match_score_updated

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        self._image_lock = threading.Lock()
        self._current_image: Optional[np.ndarray[Any, Any]] = None

        self._flow_enabled = True
        self._flow_hotkey_vk_codes: List[int] = []
        self._flow_hotkey_is_currently_held = False

        self._activation_engine = ActivationEngine()

    def Start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="TriggerMonitorService", daemon=True)
        self._thread.start()

    def Stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._thread = None

    def SetImage(self, image: Optional[np.ndarray[Any, Any]]) -> None:
        with self._image_lock:
            self._current_image = image

    def SetFlowEnabled(self, is_enabled: bool) -> None:
        self._flow_enabled = is_enabled
        if self._on_flow_state_changed is not None:
            self._on_flow_state_changed(self._flow_enabled)

    def ToggleFlowEnabled(self) -> None:
        self.SetFlowEnabled(not self._flow_enabled)

    def SetFlowHotkey(self, virtual_key_codes: List[int]) -> None:
        self._flow_hotkey_vk_codes = list(virtual_key_codes)
        if self._on_flow_hotkey_changed is not None:
            self._on_flow_hotkey_changed(list(self._flow_hotkey_vk_codes))

    def GetFlowHotkey(self) -> List[int]:
        return list(self._flow_hotkey_vk_codes)

    def _copy_image_for_processing(self) -> Optional[np.ndarray[Any, Any]]:
        with self._image_lock:
            local_image = self._current_image
            self._current_image = None
            return local_image

    def _check_flow_hotkey_pressed(self) -> None:
        if self._flow_hotkey_vk_codes:
            is_down_now = IsHotkeyActive(self._flow_hotkey_vk_codes)
            if self._flow_hotkey_is_currently_held and not is_down_now:
                self.ToggleFlowEnabled()
            self._flow_hotkey_is_currently_held = is_down_now
        else:
            self._flow_hotkey_is_currently_held = False

    def _run(self) -> None:
        while not self._stop_event.is_set():
            self._check_flow_hotkey_pressed()

            if not self._flow_enabled:
                time.sleep(self._poll_interval_ms / 1000.0)
                continue

            local_image = self._copy_image_for_processing()
            event_items_snapshot = list(self._get_event_items())

            activation = self._activation_engine.loop(event_items_snapshot, local_image)

            if self._on_event_triggered is not None:
                for event in activation.triggered:
                    self._on_event_triggered(event)

            if self._on_event_disabled is not None:
                for event in activation.disabled:
                    self._on_event_disabled(event)

            if self._on_match_score_updated is not None:
                for update in activation.match_updates:
                    self._on_match_score_updated(update)

            time.sleep(self._poll_interval_ms / 1000.0)


class LiveCaptureService:
    def __init__(
        self,
        window_handle: int,
        interval_ms: int = 200,
        on_image: Optional[Callable[[Optional[np.ndarray[Any, Any]]], None]] = None,
    ) -> None:
        self._window_handle = window_handle
        self._interval_ms = interval_ms
        self._on_image = on_image

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def Start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="LiveCaptureService", daemon=True)
        self._thread.start()

    def Stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._thread = None

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                image = CaptureWindowByHwnd(self._window_handle)
            except Exception as e:
                print(f"Live capture error: {e}")
                image = None
                self._stop_event.set()

            if self._on_image is not None:
                self._on_image(image)

            time.sleep(self._interval_ms / 1000.0)