from enum import Enum, auto
import queue
import threading
import time
from dataclasses import dataclass
from typing import Optional, cast

import numpy as np
from numpy.typing import NDArray

from Src.Helper import *


@dataclass(frozen=True)
class _ControlAction:
    kind: str
    x: float
    y: float
    key: str = ""

@dataclass(frozen=True)
class ConditionRoi:
    xNormalized: float
    yNormalized: float
    widthNormalized: float
    heightNormalized: float


class ConditionType(Enum):
    ImageMatchRoi = auto()
    ProgressBar = auto()


@dataclass(frozen=True)
class ConditionItem:
    name: str
    roi: ConditionRoi
    type: ConditionType
    templateImage: Optional[np.ndarray[Any, Any]] = None

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

        # Control (macro) queue executed by a dedicated worker thread.
        self._control_queue: queue.Queue[_ControlAction] = queue.Queue(maxsize=256)
        self._control_last_error: Optional[BaseException] = None
        self._control_thread = threading.Thread(
            target=self._control_worker,
            name="SentinelFlowControl",
            daemon=True,
        )
        self._control_thread.start()

        self._conditionItemList : List[ConditionItem] = []

    def GetConditionItems(self) -> List[ConditionItem]:
        with self._state_lock:
            return list(self._conditionItemList)

    def ClearConditionItems(self) -> None:
        with self._state_lock:
            self._conditionItemList.clear()

    def AddConditionItem(self, item: ConditionItem) -> None:
        with self._state_lock:
            self._conditionItemList.append(item)

    def RemoveConditionItemsByName(self, name: str) -> int:
        target = (name or "").strip()
        if not target:
            return 0

        with self._state_lock:
            before = len(self._conditionItemList)
            self._conditionItemList = [ci for ci in self._conditionItemList if ci.name != target]
            return before - len(self._conditionItemList)

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

        # Drain any queued control actions for the closed app.
        try:
            while True:
                self._control_queue.get_nowait()
                self._control_queue.task_done()
        except queue.Empty:
            pass

    def _control_worker(self) -> None:
        while True:
            action = self._control_queue.get()
            print("Processing control action:", action)
            try:
                if action.kind == "click":
                    self._execute_click(action.x, action.y)
                elif action.kind == "key":
                    self._execute_key(action.key)
            except BaseException as exc:
                with self._state_lock:
                    print("Control action error:", exc)
                    self._control_last_error = exc
            finally:
                self._control_queue.task_done()

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

    def _execute_click(self, normalizedX: float, normalizedY: float) -> None:
        x = float(max(0.0, min(1.0, normalizedX)))
        y = float(max(0.0, min(1.0, normalizedY)))

        with self._state_lock:
            hwnd = self._hwnd

        if hwnd == 0:
            raise Exception("No application is attached for control.")

        SendMouseClickToWindow(hwnd, x, y)

    def EnqueueClick(self, normalizedX: float, normalizedY: float) -> None:
        action = _ControlAction(kind="click", x=float(normalizedX), y=float(normalizedY))
        try:
            self._control_queue.put_nowait(action)
        except queue.Full:
            # KISS stability: drop oldest action and enqueue newest.
            try:
                self._control_queue.get_nowait()
                self._control_queue.task_done()
            except queue.Empty:
                pass
            try:
                self._control_queue.put_nowait(action)
            except queue.Full:
                pass

    def _execute_key(self, keyName: str) -> None:
        name = (keyName or "").strip()
        if not name:
            raise ValueError("keyName cannot be empty")

        with self._state_lock:
            hwnd = self._hwnd

        if hwnd == 0:
            raise Exception("No application is attached for control.")

        vk = VkFromKeyName(name)
        SendKeystrokeToWindow(hwnd, vk)

    def EnqueueKeyStroke(self, keyName: str) -> None:
        action = _ControlAction(kind="key", x=0.0, y=0.0, key=str(keyName))
        try:
            self._control_queue.put_nowait(action)
        except queue.Full:
            # Same policy: drop oldest and keep newest.
            try:
                self._control_queue.get_nowait()
                self._control_queue.task_done()
            except queue.Empty:
                pass
            try:
                self._control_queue.put_nowait(action)
            except queue.Full:
                pass

    def GetLastControlError(self) -> Optional[BaseException]:
        with self._state_lock:
            return self._control_last_error
        
