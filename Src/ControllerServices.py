import threading
import time
from typing import Optional, cast

import numpy as np
from numpy.typing import NDArray

from Src.Helper import *


class ControllerServices:
    def __init__(self):
        self._pid: PID = 0
        self._hwnd: HWND = 0

        self._state_lock = threading.Lock()

        self._capture_thread: Optional[threading.Thread] = None
        self._capture_enabled_event = threading.Event()
        self._capture_interval_seconds = 1.0
        self._capture_lock = threading.Lock()
        self._latest_capture: Optional[NDArray[np.uint8]] = None
        self._capture_last_error: Optional[BaseException] = None
        self._capture_seq = 0

        # Create the capture worker thread at startup to avoid runtime thread-creation instability.
        self._capture_thread = threading.Thread(
            target=self._capture_worker,
            name="SentinelFlowCapture",
            daemon=True,
        )
        self._capture_thread.start()

    def LaunchApp(self, app_path: str, left: int = 0, top: int = 0, width: int = 640, height: int = 480) -> None:
        self.LaucnhApp(app_path, left=left, top=top, width=width, height=height)

    def LaucnhApp(self, app_path: str, left: int = 0, top: int = 0, width: int = 640, height: int = 480) -> None:
        self._pid = LaunchProcessByExecutable(app_path)
        foundHwnd = FindHwndByPid(self._pid)
        if foundHwnd is None:
            raise Exception("Failed to find window handle for launched application.")
        with self._state_lock:
            self._hwnd = foundHwnd

        if width <= 0 or height <= 0:
            raise ValueError("width and height must be > 0")
        ResizeAndRepositionWindow(self._hwnd, int(left), int(top), int(width), int(height))

    def AttachApp(self, window_title: str, left: int = 0, top: int = 0, width: int = 640, height: int = 480) -> None:
        foundHwnd = FindHwndByTitle(window_title)
        if foundHwnd is None:
            raise Exception("Failed to find window handle for the specified title.")
        with self._state_lock:
            self._hwnd = foundHwnd
            self._pid = FindPidByHwnd(self._hwnd)

        if width <= 0 or height <= 0:
            raise ValueError("width and height must be > 0")
        ResizeAndRepositionWindow(self._hwnd, int(left), int(top), int(width), int(height))

    def CloseApp(self) -> None:
        # Ensure any capture loop is stopped before tearing down the window/process.
        self.StopCapture()
        pidToKill: PID = 0
        with self._state_lock:
            pidToKill = self._pid
            self._pid = 0
            self._hwnd = 0

        if pidToKill != 0:
            TerminateProcessByPid(pidToKill)

    def _capture_worker(self) -> None:
        # KISS: one daemon thread for the lifetime of Services.
        # It blocks until capture is enabled, then captures every interval.
        while True:
            self._capture_enabled_event.wait()

            while self._capture_enabled_event.is_set():
                with self._state_lock:
                    hwnd = self._hwnd
                    interval = float(self._capture_interval_seconds)

                if interval <= 0:
                    interval = 1.0

                if hwnd == 0:
                    with self._capture_lock:
                        self._capture_last_error = Exception("No application is attached for capturing.")
                    time.sleep(interval)
                    continue

                try:
                    frame = CaptureWindowByHwnd(hwnd)
                    with self._capture_lock:
                        self._latest_capture = cast(NDArray[np.uint8], frame)
                        self._capture_last_error = None
                        self._capture_seq += 1
                except BaseException as exc:
                    with self._capture_lock:
                        self._capture_last_error = exc

                time.sleep(interval)

    def StartCapture(self, intervalSeconds: float = 1.0) -> None:
        if intervalSeconds <= 0:
            raise ValueError("intervalSeconds must be > 0")

        with self._state_lock:
            if self._hwnd == 0:
                raise Exception("No application is attached for capturing.")
            self._capture_interval_seconds = float(intervalSeconds)

        self._capture_enabled_event.set()
        
    def StopCapture(self) -> None:
        # Only disables capture; the worker thread remains alive.
        self._capture_enabled_event.clear()

    def GetLatestCapture(self) -> Optional[NDArray[np.uint8]]:
        with self._capture_lock:
            if self._latest_capture is None:
                return None
            # Defensive copy so callers can't mutate internal state.
            return self._latest_capture.copy()

    def GetCaptureSequence(self) -> int:
        with self._capture_lock:
            return int(self._capture_seq)

    def GetLastCaptureError(self) -> Optional[BaseException]:
        with self._capture_lock:
            return self._capture_last_error
        
