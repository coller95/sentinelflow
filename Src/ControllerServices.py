from enum import Enum, auto
import base64
import queue
import threading
import time
from dataclasses import dataclass
from typing import Optional, cast, Dict, List, Any
from uuid import UUID, uuid4

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
    uuid: UUID
    name: str
    roi: ConditionRoi
    type: ConditionType
    templateImage: Optional[np.ndarray[Any, Any]] = None


@dataclass(frozen=True)
class ConditionStatusSnapshot:
    uuid: UUID
    name: str
    type: ConditionType
    templateThumbBase64: Optional[str]
    cropThumbBase64: Optional[str]
    last: Optional[float]


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

        # Dict preserves insertion order (Python 3.7+). We also rely on it for up/down moves.
        self._conditionItemList: Dict[UUID, ConditionItem] = {}

        # Condition status computation (template/crop/last) on a dedicated worker.
        self._condition_status_lock = threading.Lock()
        self._condition_status: Dict[UUID, ConditionStatusSnapshot] = {}
        self._condition_status_seq = 0
        self._condition_status_interval_seconds = 0.5
        self._condition_status_thread = threading.Thread(
            target=self._condition_status_worker,
            name="SentinelFlowConditionStatus",
            daemon=True,
        )
        self._condition_status_thread.start()

    def GetConditionItems(self) -> List[ConditionItem]:
        with self._state_lock:
            return list(self._conditionItemList.values())

    def _condition_keys_in_order(self) -> List[UUID]:
        return list(self._conditionItemList.keys())

    def _reorder_conditions_by_keys(self, keys: List[UUID]) -> None:
        # Rebuild dict to apply new order.
        self._conditionItemList = {k: self._conditionItemList[k] for k in keys}

    def GetConditionStatusSnapshots(self) -> List[ConditionStatusSnapshot]:
        """Return status snapshots in current condition order."""
        with self._condition_status_lock:
            # Values preserve insertion order of the dict we build in the worker.
            return list(self._condition_status.values())

    def GetConditionStatusSnapshotDict(self) -> Dict[UUID, ConditionStatusSnapshot]:
        """Return a copy of the snapshot dict keyed by uuid."""
        with self._condition_status_lock:
            return dict(self._condition_status)

    def GetConditionStatusSequence(self) -> int:
        with self._condition_status_lock:
            return int(self._condition_status_seq)

    def SetConditionStatusIntervalSeconds(self, intervalSeconds: float) -> None:
        if intervalSeconds <= 0:
            raise ValueError("intervalSeconds must be > 0")
        with self._state_lock:
            self._condition_status_interval_seconds = float(intervalSeconds)

    def GetConditionItem(self, index: int) -> Optional[ConditionItem]:
        with self._state_lock:
            keys = self._condition_keys_in_order()
            if index < 0 or index >= len(keys):
                return None
            return self._conditionItemList.get(keys[index])

    def GetConditionItemByUuid(self, uuid: UUID) -> Optional[ConditionItem]:
        with self._state_lock:
            return self._conditionItemList.get(uuid)

    def SetConditionItem(self, index: int, item: ConditionItem) -> None:
        with self._state_lock:
            keys = self._condition_keys_in_order()
            if index < 0 or index >= len(keys):
                raise IndexError("Condition index out of range")

            existing_uuid = keys[index]
            # Keep the existing UUID at this position.
            if item.uuid != existing_uuid:
                item = ConditionItem(
                    uuid=existing_uuid,
                    name=item.name,
                    roi=item.roi,
                    type=item.type,
                    templateImage=item.templateImage,
                )
            self._conditionItemList[existing_uuid] = item

    def SetConditionItemByUuid(self, uuid: UUID, item: ConditionItem) -> None:
        with self._state_lock:
            if uuid not in self._conditionItemList:
                raise KeyError("Condition uuid not found")
            if item.uuid != uuid:
                item = ConditionItem(
                    uuid=uuid,
                    name=item.name,
                    roi=item.roi,
                    type=item.type,
                    templateImage=item.templateImage,
                )
            self._conditionItemList[uuid] = item

    def ClearConditionItems(self) -> None:
        with self._state_lock:
            self._conditionItemList.clear()

    def AddConditionItem(self, item: ConditionItem) -> None:
        with self._state_lock:
            self._conditionItemList[item.uuid] = item

    def AddConditionItemNewUuid(
        self,
        name: str,
        roi: ConditionRoi,
        type: ConditionType,
        templateImage: Optional[np.ndarray[Any, Any]] = None,
    ) -> ConditionItem:
        new_item = ConditionItem(uuid=uuid4(), name=name, roi=roi, type=type, templateImage=templateImage)
        self.AddConditionItem(new_item)
        return new_item

    def RemoveConditionItemsByName(self, name: str) -> int:
        target = (name or "").strip()
        if not target:
            return 0

        with self._state_lock:
            before = len(self._conditionItemList)
            keys_to_delete = [k for k, ci in self._conditionItemList.items() if ci.name == target]
            for k in keys_to_delete:
                del self._conditionItemList[k]
            return before - len(self._conditionItemList)

    def RemoveConditionItemByIndex(self, index: int) -> None:
        with self._state_lock:
            keys = self._condition_keys_in_order()
            if index < 0 or index >= len(keys):
                raise IndexError("Condition index out of range")
            del self._conditionItemList[keys[index]]

    def RemoveConditionItemByUuid(self, uuid: UUID) -> None:
        with self._state_lock:
            if uuid not in self._conditionItemList:
                raise KeyError("Condition uuid not found")
            del self._conditionItemList[uuid]

    def MoveConditionItem(self, index: int, direction: str) -> int:
        """Move a condition up/down. Returns new index."""
        dir_norm = (direction or "").strip().lower()
        with self._state_lock:
            keys = self._condition_keys_in_order()
            n = len(keys)
            if index < 0 or index >= n:
                raise IndexError("Condition index out of range")

            if dir_norm == "up":
                if index == 0:
                    return 0
                keys[index - 1], keys[index] = keys[index], keys[index - 1]
                self._reorder_conditions_by_keys(keys)
                return index - 1

            if dir_norm == "down":
                if index >= n - 1:
                    return n - 1
                keys[index + 1], keys[index] = keys[index], keys[index + 1]
                self._reorder_conditions_by_keys(keys)
                return index + 1

            raise ValueError("direction must be 'up' or 'down'")

    def MoveConditionItemByUuid(self, uuid: UUID, direction: str) -> None:
        dir_norm = (direction or "").strip().lower()
        with self._state_lock:
            keys = self._condition_keys_in_order()
            if uuid not in self._conditionItemList:
                raise KeyError("Condition uuid not found")

            index = keys.index(uuid)
            n = len(keys)

            if dir_norm == "up":
                if index == 0:
                    return
                keys[index - 1], keys[index] = keys[index], keys[index - 1]
                self._reorder_conditions_by_keys(keys)
                return

            if dir_norm == "down":
                if index >= n - 1:
                    return
                keys[index + 1], keys[index] = keys[index], keys[index + 1]
                self._reorder_conditions_by_keys(keys)
                return

            raise ValueError("direction must be 'up' or 'down'")

    def _encode_thumb_b64(self, img: np.ndarray[Any, Any], maxSize: int = 64) -> Optional[str]:
        if getattr(img, "size", 0) == 0:
            return None
        h, w = img.shape[:2]
        if h <= 0 or w <= 0:
            return None

        scale = float(maxSize) / float(max(h, w))
        out = img
        if scale < 1.0:
            new_w = max(1, int(round(w * scale)))
            new_h = max(1, int(round(h * scale)))
            out = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

        ok, encoded = cv2.imencode(".jpg", out)
        if not ok:
            return None
        return base64.b64encode(encoded.tobytes()).decode("ascii")

    def _crop_frame(self, frame: NDArray[np.uint8], roi: ConditionRoi) -> NDArray[np.uint8]:
        imageHeight, imageWidth = frame.shape[:2]

        x = float(max(0.0, min(1.0, roi.xNormalized)))
        y = float(max(0.0, min(1.0, roi.yNormalized)))
        rw = float(max(0.0, min(1.0, roi.widthNormalized)))
        rh = float(max(0.0, min(1.0, roi.heightNormalized)))

        pixelX = int(x * imageWidth)
        pixelY = int(y * imageHeight)
        pixelW = int(rw * imageWidth)
        pixelH = int(rh * imageHeight)

        pixelX = max(0, min(pixelX, imageWidth - 1))
        pixelY = max(0, min(pixelY, imageHeight - 1))
        pixelW = max(1, min(pixelW, imageWidth - pixelX))
        pixelH = max(1, min(pixelH, imageHeight - pixelY))

        return frame[pixelY : pixelY + pixelH, pixelX : pixelX + pixelW].copy()

    def _condition_status_worker(self) -> None:
        while True:
            with self._state_lock:
                interval = float(self._condition_status_interval_seconds)
            if interval <= 0:
                interval = 0.5

            # Snapshot conditions.
            with self._state_lock:
                items = list(self._conditionItemList.values())

            # Snapshot latest capture.
            with self._capture_lock:
                frame = self._latest_capture.copy() if self._latest_capture is not None else None

            snapshots: List[ConditionStatusSnapshot] = []

            for item in items:
                template_thumb = self._encode_thumb_b64(item.templateImage) if item.templateImage is not None else None

                crop_thumb: Optional[str] = None
                last: Optional[float] = None

                if frame is not None:
                    try:
                        crop = self._crop_frame(frame, item.roi)
                        crop_thumb = self._encode_thumb_b64(crop)

                        if item.type == ConditionType.ImageMatchRoi:
                            if item.templateImage is not None:
                                last = float(MatchTemplate(crop, item.templateImage))
                        elif item.type == ConditionType.ProgressBar:
                            last = float(EstimateProgressBarPercentage(crop))
                    except BaseException:
                        crop_thumb = None
                        last = None

                snapshots.append(
                    ConditionStatusSnapshot(
                        uuid=item.uuid,
                        name=item.name,
                        type=item.type,
                        templateThumbBase64=template_thumb,
                        cropThumbBase64=crop_thumb,
                        last=last,
                    )
                )

            with self._condition_status_lock:
                # Store as dict keyed by UUID, preserving the order of `items`.
                self._condition_status = {s.uuid: s for s in snapshots}
                self._condition_status_seq += 1

            time.sleep(interval)

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
        
