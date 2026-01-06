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

class MacroType(Enum):
    Click = auto()
    KeyStroke = auto()
    Delay = auto()

@dataclass(frozen=True)
class MacroStep:
    action: MacroType
    parameters: Dict[str, Any]

@dataclass(frozen=True)
class ActionItem:
    uuid: UUID
    name: str
    steps: List[MacroStep]

class TriggerComparator(Enum):
    Equals = auto()
    NotEquals = auto()
    GreaterThan = auto()
    LessThan = auto()
    GreaterThanOrEqual = auto()
    LessThanOrEqual = auto()

@dataclass(frozen=True)
class TriggerCiteria:
    conditionUuid: UUID
    expectedValue: Any
    comparator: TriggerComparator

@dataclass(frozen=True)
class TriggerItem:
    uuid: UUID
    name: str
    triggerCiterias: List[TriggerCiteria]  # List of ConditionItem UUIDs
    action: UUID            # ActionItem UUID
    enabled: bool = False
    retriggerMs: int = 0

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

        # Action (macro) definitions and execution.
        self._actionItemList: Dict[UUID, ActionItem] = {}
        self._macro_queue: queue.Queue[UUID] = queue.Queue(maxsize=64)
        self._macro_last_error: Optional[BaseException] = None
        self._macro_current_action_uuid: Optional[UUID] = None
        self._macro_current_started_unix: Optional[float] = None
        self._macro_last_enqueued_action_uuid: Optional[UUID] = None
        self._macro_last_enqueued_unix: Optional[float] = None
        self._macro_last_completed_action_uuid: Optional[UUID] = None
        self._macro_last_completed_unix: Optional[float] = None
        self._action_run_count: Dict[UUID, int] = {}
        self._action_last_started_unix: Dict[UUID, float] = {}
        self._action_last_completed_unix: Dict[UUID, float] = {}
        self._macro_thread = threading.Thread(
            target=self._macro_worker,
            name="SentinelFlowMacro",
            daemon=True,
        )
        self._macro_thread.start()

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

        # Trigger definitions and evaluation.
        self._triggerItemList: Dict[UUID, TriggerItem] = {}
        self._trigger_last_error: Optional[BaseException] = None
        self._trigger_interval_seconds = 0.2
        self._trigger_last_match: Dict[UUID, bool] = {}
        self._trigger_fire_count: Dict[UUID, int] = {}
        self._trigger_last_fire_unix: Dict[UUID, float] = {}
        self._trigger_last_fire_mono: Dict[UUID, float] = {}
        self._trigger_last_eval: Dict[UUID, List[Dict[str, Any]]] = {}
        self._trigger_status_seq: int = 0
        self._trigger_thread = threading.Thread(
            target=self._trigger_worker,
            name="SentinelFlowTrigger",
            daemon=True,
        )
        self._trigger_thread.start()

    def GetConditionItems(self) -> List[ConditionItem]:
        with self._state_lock:
            return list(self._conditionItemList.values())

    def GetActionItems(self) -> List[ActionItem]:
        with self._state_lock:
            return list(self._actionItemList.values())

    def GetTriggerItems(self) -> List[TriggerItem]:
        with self._state_lock:
            return list(self._triggerItemList.values())

    def GetTriggerItemByUuid(self, uuid: UUID) -> Optional[TriggerItem]:
        with self._state_lock:
            return self._triggerItemList.get(uuid)

    def UpsertTriggerItem(
        self,
        uuid: Optional[UUID],
        name: str,
        triggerCiterias: List[TriggerCiteria],
        action: UUID,
        enabled: bool = False,
        retriggerMs: int = 0,
    ) -> TriggerItem:
        clean_name = (name or "").strip()
        if not clean_name:
            raise ValueError("name cannot be empty")

        retrigger_ms_int = int(retriggerMs or 0)
        if retrigger_ms_int < 0:
            raise ValueError("retriggerMs cannot be negative")

        with self._state_lock:
            if action not in self._actionItemList:
                raise KeyError("Action uuid not found")

            # Best-effort validation: criteria condition UUIDs must exist.
            for c in triggerCiterias or []:
                if c.conditionUuid not in self._conditionItemList:
                    raise KeyError("Condition uuid not found")

            trig_uuid = uuid or uuid4()
            item = TriggerItem(
                uuid=trig_uuid,
                name=clean_name,
                triggerCiterias=list(triggerCiterias or []),
                action=action,
                enabled=bool(enabled),
                retriggerMs=retrigger_ms_int,
            )
            self._triggerItemList[trig_uuid] = item
            return item

    def SetTriggerEnabled(self, uuid: UUID, enabled: bool) -> TriggerItem:
        with self._state_lock:
            existing = self._triggerItemList.get(uuid)
            if existing is None:
                raise KeyError("Trigger uuid not found")
            updated = TriggerItem(
                uuid=existing.uuid,
                name=existing.name,
                triggerCiterias=list(existing.triggerCiterias or []),
                action=existing.action,
                enabled=bool(enabled),
                retriggerMs=int(getattr(existing, "retriggerMs", 0) or 0),
            )
            self._triggerItemList[uuid] = updated
            return updated

    def GetTriggerStatusSnapshot(self) -> List[Dict[str, Any]]:
        with self._state_lock:
            triggers = list(self._triggerItemList.values())
            actions_by_uuid = {a.uuid: a for a in self._actionItemList.values()}
            last_match = dict(self._trigger_last_match)
            fire_count = dict(self._trigger_fire_count)
            last_fire = dict(self._trigger_last_fire_unix)
            last_eval = dict(self._trigger_last_eval)

        # Pull action execution stats outside the lock (it locks internally).
        action_stats = self.GetActionExecutionStats()

        out: List[Dict[str, Any]] = []
        for t in triggers:
            a = actions_by_uuid.get(t.action)
            a_name = a.name if a is not None else str(t.action)
            a_stat = action_stats.get(t.action, {
                "runCount": 0,
                "lastStartedUnix": None,
                "lastCompletedUnix": None,
                "isRunning": False,
            })

            lf = last_fire.get(t.uuid)
            eval_rows = last_eval.get(t.uuid, [])

            out.append({
                "uuid": str(t.uuid),
                "name": t.name,
                "enabled": bool(t.enabled),
                "retriggerMs": int(getattr(t, "retriggerMs", 0) or 0),
                "isMet": bool(last_match.get(t.uuid, False)),
                "fireCount": int(fire_count.get(t.uuid, 0)),
                "lastFireUnix": (float(lf) if lf is not None else None),
                "eval": eval_rows,
                "actionUuid": str(t.action),
                "actionName": a_name,
                "actionIsRunning": bool(a_stat.get("isRunning", False)),
                "actionRunCount": int(a_stat.get("runCount", 0)),
                "actionLastStartedUnix": a_stat.get("lastStartedUnix", None),
                "actionLastCompletedUnix": a_stat.get("lastCompletedUnix", None),
            })

        return out

    def GetTriggerStatusSequence(self) -> int:
        with self._state_lock:
            return int(self._trigger_status_seq)

    def RemoveTriggerItemByUuid(self, uuid: UUID) -> None:
        with self._state_lock:
            if uuid not in self._triggerItemList:
                raise KeyError("Trigger uuid not found")
            del self._triggerItemList[uuid]
            self._trigger_last_match.pop(uuid, None)
            self._trigger_fire_count.pop(uuid, None)
            self._trigger_last_fire_unix.pop(uuid, None)
            self._trigger_last_fire_mono.pop(uuid, None)
            self._trigger_last_eval.pop(uuid, None)

    def GetLastTriggerError(self) -> Optional[BaseException]:
        with self._state_lock:
            return self._trigger_last_error

    def GetTriggerLastMatchDict(self) -> Dict[UUID, bool]:
        with self._state_lock:
            return dict(self._trigger_last_match)

    def GetTriggerFireCountDict(self) -> Dict[UUID, int]:
        with self._state_lock:
            return dict(self._trigger_fire_count)

    def GetTriggerLastFireUnixDict(self) -> Dict[UUID, float]:
        with self._state_lock:
            return dict(self._trigger_last_fire_unix)

    def GetMacroQueueSize(self) -> int:
        try:
            return int(self._macro_queue.qsize())
        except Exception:
            return 0

    def _trigger_worker(self) -> None:
        def to_float(v: Any) -> Optional[float]:
            try:
                if v is None:
                    return None
                return float(v)
            except Exception:
                return None

        def eval_one(last_value: Optional[float], expected: Any, comp: TriggerComparator) -> bool:
            if last_value is None:
                return False

            lv = float(last_value)

            if comp in (TriggerComparator.GreaterThan, TriggerComparator.LessThan,
                        TriggerComparator.GreaterThanOrEqual, TriggerComparator.LessThanOrEqual):
                ev = to_float(expected)
                if ev is None:
                    return False
                if comp == TriggerComparator.GreaterThan:
                    return lv > ev
                if comp == TriggerComparator.LessThan:
                    return lv < ev
                if comp == TriggerComparator.GreaterThanOrEqual:
                    return lv >= ev
                if comp == TriggerComparator.LessThanOrEqual:
                    return lv <= ev
                return False

            # Equals / NotEquals: prefer numeric comparison if possible.
            evf = to_float(expected)
            if evf is not None:
                ok = (lv == evf)
            else:
                ok = (str(lv) == str(expected))

            if comp == TriggerComparator.Equals:
                return ok
            if comp == TriggerComparator.NotEquals:
                return not ok

            return False

        while True:
            try:
                # Clear stale errors after we successfully enter the loop.
                with self._state_lock:
                    self._trigger_last_error = None

                with self._state_lock:
                    interval = float(self._trigger_interval_seconds)
                    triggers = list(self._triggerItemList.values())

                # Snapshot condition names.
                with self._state_lock:
                    cond_name_by_uuid: Dict[UUID, str] = {k: v.name for k, v in self._conditionItemList.items()}

                # Snapshot last values by condition UUID.
                with self._condition_status_lock:
                    last_by_uuid: Dict[UUID, Optional[float]] = {k: v.last for k, v in self._condition_status.items()}

                for t in triggers:
                    eval_rows: List[Dict[str, Any]] = []
                    if not bool(t.enabled):
                        with self._state_lock:
                            self._trigger_last_match[t.uuid] = False
                            self._trigger_last_eval[t.uuid] = []
                        continue

                    matched = True
                    for c in (t.triggerCiterias or []):
                        last_val = last_by_uuid.get(c.conditionUuid)
                        ok = eval_one(last_val, c.expectedValue, c.comparator)
                        eval_rows.append({
                            "conditionUuid": str(c.conditionUuid),
                            "conditionName": cond_name_by_uuid.get(c.conditionUuid, str(c.conditionUuid)),
                            "comparator": c.comparator.name,
                            "expected": c.expectedValue,
                            "last": last_val,
                            "ok": bool(ok),
                        })
                        if not ok:
                            matched = False
                            break

                    with self._state_lock:
                        prev = bool(self._trigger_last_match.get(t.uuid, False))
                        self._trigger_last_match[t.uuid] = bool(matched)
                        self._trigger_last_eval[t.uuid] = eval_rows

                    # Fire policy:
                    # - retriggerMs <= 0: rising-edge only (prevents spamming)
                    # - retriggerMs  > 0: allow periodic fire while still matched
                    should_fire = False
                    retrigger_ms = int(getattr(t, "retriggerMs", 0) or 0)
                    if matched:
                        if retrigger_ms > 0:
                            now_mono = float(time.monotonic())
                            with self._state_lock:
                                last_mono = self._trigger_last_fire_mono.get(t.uuid)
                            if last_mono is None:
                                should_fire = True
                            else:
                                if (now_mono - float(last_mono)) >= (float(retrigger_ms) / 1000.0):
                                    should_fire = True
                        else:
                            if not prev:
                                should_fire = True

                    if should_fire:
                        try:
                            self.EnqueueRunActionByUuid(t.action)
                            now_unix = float(time.time())
                            now_mono = float(time.monotonic())
                            with self._state_lock:
                                self._trigger_fire_count[t.uuid] = int(self._trigger_fire_count.get(t.uuid, 0)) + 1
                                self._trigger_last_fire_unix[t.uuid] = now_unix
                                self._trigger_last_fire_mono[t.uuid] = now_mono
                        except Exception as exc:
                            with self._state_lock:
                                self._trigger_last_error = exc

                with self._state_lock:
                    self._trigger_status_seq += 1

                time.sleep(max(0.05, interval))

            except BaseException as exc:
                with self._state_lock:
                    self._trigger_last_error = exc
                time.sleep(0.5)

    def GetActionItemByUuid(self, uuid: UUID) -> Optional[ActionItem]:
        with self._state_lock:
            return self._actionItemList.get(uuid)

    def UpsertActionItem(self, uuid: Optional[UUID], name: str, steps: List[MacroStep]) -> ActionItem:
        clean_name = (name or "").strip()
        if not clean_name:
            raise ValueError("name cannot be empty")

        with self._state_lock:
            action_uuid = uuid or uuid4()
            item = ActionItem(uuid=action_uuid, name=clean_name, steps=list(steps))
            self._actionItemList[action_uuid] = item
            return item

    def RemoveActionItemByUuid(self, uuid: UUID) -> None:
        with self._state_lock:
            if uuid not in self._actionItemList:
                raise KeyError("Action uuid not found")
            del self._actionItemList[uuid]

    def EnqueueRunActionByUuid(self, uuid: UUID) -> None:
        with self._state_lock:
            if uuid not in self._actionItemList:
                raise KeyError("Action uuid not found")
            self._macro_last_enqueued_action_uuid = uuid
            self._macro_last_enqueued_unix = float(time.time())

        try:
            self._macro_queue.put_nowait(uuid)
        except queue.Full:
            # Drop oldest and enqueue newest.
            try:
                self._macro_queue.get_nowait()
                self._macro_queue.task_done()
            except queue.Empty:
                pass
            try:
                self._macro_queue.put_nowait(uuid)
            except queue.Full:
                pass

    def GetLastMacroError(self) -> Optional[BaseException]:
        with self._state_lock:
            return self._macro_last_error

    def GetMacroState(self) -> Dict[str, Any]:
        with self._state_lock:
            return {
                "currentActionUuid": (str(self._macro_current_action_uuid) if self._macro_current_action_uuid else None),
                "currentStartedUnix": (float(self._macro_current_started_unix) if self._macro_current_started_unix else None),
                "lastEnqueuedActionUuid": (str(self._macro_last_enqueued_action_uuid) if self._macro_last_enqueued_action_uuid else None),
                "lastEnqueuedUnix": (float(self._macro_last_enqueued_unix) if self._macro_last_enqueued_unix else None),
                "lastCompletedActionUuid": (str(self._macro_last_completed_action_uuid) if self._macro_last_completed_action_uuid else None),
                "lastCompletedUnix": (float(self._macro_last_completed_unix) if self._macro_last_completed_unix else None),
            }

    def GetActionExecutionStats(self) -> Dict[UUID, Dict[str, Any]]:
        with self._state_lock:
            out: Dict[UUID, Dict[str, Any]] = {}
            for au in set(
                list(self._actionItemList.keys())
                + list(self._action_run_count.keys())
                + list(self._action_last_started_unix.keys())
                + list(self._action_last_completed_unix.keys())
            ):
                last_started = self._action_last_started_unix.get(au)
                last_completed = self._action_last_completed_unix.get(au)
                out[au] = {
                    "runCount": int(self._action_run_count.get(au, 0)),
                    "lastStartedUnix": (float(last_started) if last_started is not None else None),
                    "lastCompletedUnix": (float(last_completed) if last_completed is not None else None),
                    "isRunning": bool(self._macro_current_action_uuid == au),
                }
            return out

    def _macro_worker(self) -> None:
        while True:
            action_uuid = self._macro_queue.get()
            try:
                with self._state_lock:
                    action = self._actionItemList.get(action_uuid)
                    self._macro_current_action_uuid = action_uuid
                    now = float(time.time())
                    self._macro_current_started_unix = now
                    self._action_run_count[action_uuid] = int(self._action_run_count.get(action_uuid, 0)) + 1
                    self._action_last_started_unix[action_uuid] = now

                if action is None:
                    continue

                for step in action.steps:
                    if step.action == MacroType.Click:
                        x = step.parameters.get("x", step.parameters.get("xNormalized", 0.0))
                        y = step.parameters.get("y", step.parameters.get("yNormalized", 0.0))
                        self._execute_click(float(x), float(y))
                    elif step.action == MacroType.KeyStroke:
                        key = step.parameters.get("keyName", step.parameters.get("key", ""))
                        self._execute_key(str(key))
                    elif step.action == MacroType.Delay:
                        if "seconds" in step.parameters:
                            seconds = float(step.parameters.get("seconds", 0.0))
                        elif "ms" in step.parameters:
                            seconds = float(step.parameters.get("ms", 0.0)) / 1000.0
                        else:
                            seconds = 0.0
                        time.sleep(max(0.0, seconds))
            except BaseException as exc:
                with self._state_lock:
                    self._macro_last_error = exc
            finally:
                with self._state_lock:
                    self._macro_last_completed_action_uuid = action_uuid
                    now2 = float(time.time())
                    self._macro_last_completed_unix = now2
                    self._action_last_completed_unix[action_uuid] = now2
                    self._macro_current_action_uuid = None
                    self._macro_current_started_unix = None
                try:
                    self._macro_queue.task_done()
                except ValueError:
                    pass

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
        
