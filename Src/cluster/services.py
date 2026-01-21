import asyncio
from enum import Enum, auto
import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, cast, Dict, List, Any, Union
from uuid import UUID, uuid4

import numpy as np
from numpy.typing import NDArray

from Src.domain.interfaces import (
    IWindowManager,
    IScreenCapturer,
    IInputController,
    IComputerVision,
)

# We need to map our internal ConditionRoi to the interface's tuple or just use the dataclass
# The interface uses Tuple[float, float, float, float].

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

    def to_tuple(self) -> Any:
        return (self.xNormalized, self.yNormalized, self.widthNormalized, self.heightNormalized)


class ConditionType(Enum):
    ImageMatchRoi = auto()
    ProgressBar = auto()


@dataclass(frozen=True)
class ConditionItem:
    uuid: UUID
    name: str
    roi: ConditionRoi
    type: ConditionType
    templateImage: Optional[NDArray[np.uint8]] = None


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

class TriggerCriteriaMode(Enum):
    All = auto()
    Any = auto()

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
    disableOnFire: bool = False
    criteriaMode: TriggerCriteriaMode = TriggerCriteriaMode.All

class ControllerServices:
    def __init__(
        self,
        window_manager: IWindowManager,
        screen_capturer: IScreenCapturer,
        input_controller: IInputController,
        computer_vision: IComputerVision,
    ):
        if not window_manager or not screen_capturer or not input_controller or not computer_vision:
             raise ValueError("All dependencies (adapters) must be provided to ControllerServices.")

        self._window_manager = window_manager
        self._screen_capturer = screen_capturer
        self._input_controller = input_controller
        self._computer_vision = computer_vision

        # Stable server identity for future centralized orchestration.
        # Persisted in state.json. Generated once if missing.
        self._server_uuid: UUID = uuid4()

        # Persisted UX defaults (so operators don't retype common values).
        self._default_app_path: str = ""
        self._default_window_title: str = ""
        self._default_window_left: int = 0
        self._default_window_top: int = 0
        self._default_window_width: int = 640
        self._default_window_height: int = 480

        self._pid: int = 0
        self._hwnd: Any = 0

        self._state_lock = threading.Lock()
        self._running = False
        self._shutdown_event = threading.Event()

        self._capture_thread: Optional[threading.Thread] = None
        self._capture_enabled_event = threading.Event()
        self._capture_interval_seconds = 1.0
        self._capture_lock = threading.Lock()
        self._latest_capture: Optional[NDArray[np.uint8]] = None
        self._capture_last_error: Optional[BaseException] = None
        self._capture_seq = 0

        # Control (macro) queue executed by a dedicated worker task.
        self._control_queue: asyncio.Queue[_ControlAction] = asyncio.Queue(maxsize=256)
        self._control_last_error: Optional[BaseException] = None
        self._control_task: Optional[asyncio.Task[None]] = None

        # Action (macro) definitions and execution.
        self._actionItemList: Dict[UUID, ActionItem] = {}
        self._macro_queue: asyncio.Queue[UUID] = asyncio.Queue(maxsize=64)
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
        self._macro_task: Optional[asyncio.Task[None]] = None

        # Dict preserves insertion order (Python 3.7+). We also rely on it for up/down moves.
        self._conditionItemList: Dict[UUID, ConditionItem] = {}

        # Condition status computation (template/crop/last) on a dedicated worker.
        self._condition_status_lock = threading.Lock()
        self._condition_status: Dict[UUID, ConditionStatusSnapshot] = {}
        self._condition_status_seq = 0
        self._condition_status_interval_seconds = 0.5
        self._condition_status_thread: Optional[threading.Thread] = None

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
        self._trigger_task: Optional[asyncio.Task[None]] = None

        # Local activation overrides (TriggerUUID -> Enabled).
        # Persisted in state.json to survive restarts and updates from Orchestrator.
        self._trigger_overrides: Dict[UUID, bool] = {}

    async def Start(self) -> None:
        if self._running:
            return
        
        self._running = True
        self._shutdown_event.clear()

        # Try to restore attachment if detached and we have a default title
        with self._state_lock:
            title = self._default_window_title
            l = self._default_window_left
            t = self._default_window_top
            w = self._default_window_width
            h = self._default_window_height
            is_detached = (self._hwnd == 0)

        if is_detached and title:
            try:
                # We use the internal method or public one? 
                # Public AttachApp updates defaults (which are already set), but handles logic.
                # It also finds PID.
                print(f"[Cluster] Auto-attaching to '{title}'...")
                self.AttachApp(title, left=l, top=t, width=w, height=h)
            except Exception as e:
                print(f"[Cluster] Auto-attach failed: {e}")
        
        # Start async tasks
        self._control_task = asyncio.create_task(self._control_worker())
        self._macro_task = asyncio.create_task(self._macro_worker())
        self._trigger_task = asyncio.create_task(self._trigger_worker())
        
        # Start persistent threads (heavy I/O or CPU)
        self._capture_thread = threading.Thread(
            target=self._capture_worker,
            name="SentinelFlowCapture",
            daemon=True,
        )
        self._capture_thread.start()
        
        self._condition_status_thread = threading.Thread(
            target=self._condition_status_worker,
            name="SentinelFlowConditionStatus",
            daemon=True,
        )
        self._condition_status_thread.start()

    async def Stop(self) -> None:
        self._running = False
        self._shutdown_event.set()
        self._capture_enabled_event.set()
        
        # Cancel async tasks
        for task in [self._control_task, self._macro_task, self._trigger_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # Wait for threads (they check _running and _shutdown_event)
        # We don't join them to avoid blocking the async loop if they are stuck,
        # but the flags should make them exit quickly.

    def GetServerUuid(self) -> UUID:
        with self._state_lock:
            return self._server_uuid

    def ResetServerUuid(self) -> UUID:
        with self._state_lock:
            self._server_uuid = uuid4()
            return self._server_uuid

    def GetAppStatus(self) -> Dict[str, Any]:
        with self._state_lock:
            attached = bool(self._hwnd)
            pid = int(self._pid) if self._pid else None
            hwnd = int(self._hwnd) if self._hwnd else None
            return {
                "attached": attached,
                "pid": pid,
                "hwnd": hwnd,
                "defaultAppPath": str(self._default_app_path or ""),
                "defaultWindowTitle": str(self._default_window_title or ""),
            }

    def GetAppDefaults(self) -> Dict[str, Any]:
        with self._state_lock:
            return {
                "defaultAppPath": str(self._default_app_path or ""),
                "defaultWindowTitle": str(self._default_window_title or ""),
                "defaultWindowLeft": int(self._default_window_left),
                "defaultWindowTop": int(self._default_window_top),
                "defaultWindowWidth": int(self._default_window_width),
                "defaultWindowHeight": int(self._default_window_height),
            }

    def SetAppDefaults(
        self,
        default_app_path: Optional[str] = None,
        default_window_title: Optional[str] = None,
        default_window_left: Optional[int] = None,
        default_window_top: Optional[int] = None,
        default_window_width: Optional[int] = None,
        default_window_height: Optional[int] = None,
    ) -> Dict[str, Any]:
        def _coerce_int(value: Optional[int], min_value: Optional[int] = None) -> Optional[int]:
            if value is None:
                return None
            try:
                n = int(value)
            except Exception:
                return None
            if min_value is not None and n < min_value:
                return None
            return n

        left = _coerce_int(default_window_left)
        top = _coerce_int(default_window_top)
        width = _coerce_int(default_window_width, min_value=1)
        height = _coerce_int(default_window_height, min_value=1)

        with self._state_lock:
            if default_app_path is not None:
                self._default_app_path = str(default_app_path or "").strip()
            if default_window_title is not None:
                self._default_window_title = str(default_window_title or "").strip()
            if left is not None:
                self._default_window_left = left
            if top is not None:
                self._default_window_top = top
            if width is not None:
                self._default_window_width = width
            if height is not None:
                self._default_window_height = height
            return {
                "defaultAppPath": str(self._default_app_path or ""),
                "defaultWindowTitle": str(self._default_window_title or ""),
                "defaultWindowLeft": int(self._default_window_left),
                "defaultWindowTop": int(self._default_window_top),
                "defaultWindowWidth": int(self._default_window_width),
                "defaultWindowHeight": int(self._default_window_height),
            }

    def ExportStateDict(self, includeServerUuid: bool = True) -> Dict[str, Any]:
        with self._state_lock:
            server_uuid = self._server_uuid
            default_app_path = self._default_app_path
            default_window_title = self._default_window_title
            default_window_left = self._default_window_left
            default_window_top = self._default_window_top
            default_window_width = self._default_window_width
            default_window_height = self._default_window_height
            conditions = list(self._conditionItemList.values())
            actions = list(self._actionItemList.values())
            triggers = list(self._triggerItemList.values())
            overrides = dict(self._trigger_overrides)

        # Use injected CV adapter
        def encode_png_b64(img: Optional[Any]) -> Optional[str]:
            if img is None:
                return None
            return self._computer_vision.encode_image_to_b64(img)

        data: Dict[str, Any] = {
            "version": 1,
            "savedAtUnix": float(time.time()),
            "app": {
                "defaultAppPath": str(default_app_path or ""),
                "defaultWindowTitle": str(default_window_title or ""),
                "defaultWindowLeft": int(default_window_left),
                "defaultWindowTop": int(default_window_top),
                "defaultWindowWidth": int(default_window_width),
                "defaultWindowHeight": int(default_window_height),
            },
            "conditions": [],
            "actions": [],
            "triggers": [],
            "triggerOverrides": {str(k): v for k, v in overrides.items()},
        }
        if includeServerUuid:
            data["serverUuid"] = str(server_uuid)

        for c in conditions:
            data["conditions"].append({
                "uuid": str(c.uuid),
                "name": c.name,
                "type": c.type.name,
                "roi": {
                    "xNormalized": float(c.roi.xNormalized),
                    "yNormalized": float(c.roi.yNormalized),
                    "widthNormalized": float(c.roi.widthNormalized),
                    "heightNormalized": float(c.roi.heightNormalized),
                },
                "templateImageBase64": encode_png_b64(c.templateImage),
            })

        for a in actions:
            steps_out: List[Dict[str, Any]] = []
            for s in (a.steps or []):
                steps_out.append({
                    "action": s.action.name,
                    "parameters": dict(s.parameters or {}),
                })
            data["actions"].append({
                "uuid": str(a.uuid),
                "name": a.name,
                "steps": steps_out,
            })

        for t in triggers:
            crit_out: List[Dict[str, Any]] = []
            for c in (t.triggerCiterias or []):
                crit_out.append({
                    "conditionUuid": str(c.conditionUuid),
                    "expectedValue": c.expectedValue,
                    "comparator": c.comparator.name,
                })
            mode = getattr(t, "criteriaMode", TriggerCriteriaMode.All)
            data["triggers"].append({
                "uuid": str(t.uuid),
                "name": t.name,
                "enabled": bool(t.enabled),
                "retriggerMs": int(getattr(t, "retriggerMs", 0) or 0),
                "disableOnFire": bool(getattr(t, "disableOnFire", False)),
                "action": str(t.action),
                "triggerCiterias": crit_out,
                "criteriaMode": mode.name,
            })

        return data

    def SaveState(self, path: Union[str, Path]) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)

        data = self.ExportStateDict(includeServerUuid=True)

        tmp = p.with_suffix(p.suffix + ".tmp")
        text = json.dumps(data, ensure_ascii=False, indent=2)
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(p)

    def ImportStateDict(self, obj: Dict[str, Any], keepServerUuid: bool = True) -> None:
        version = int(obj.get("version", 0) or 0)
        if version != 1:
            raise ValueError(f"Unsupported state version: {version}")

        app_obj = obj.get("app", {})
        if not isinstance(app_obj, dict):
            app_obj = {}
        app_obj_t: Dict[str, Any] = cast(Dict[str, Any], app_obj)
        imported_default_app_path = str(app_obj_t.get("defaultAppPath", "") or "").strip()
        imported_default_window_title = str(app_obj_t.get("defaultWindowTitle", "") or "").strip()

        def _parse_int_field(key: str, min_value: Optional[int] = None) -> Optional[int]:
            raw = app_obj_t.get(key, None)
            if raw is None:
                return None
            try:
                n = int(raw)
            except Exception:
                return None
            if min_value is not None and n < min_value:
                return None
            return n

        imported_window_left = _parse_int_field("defaultWindowLeft")
        imported_window_top = _parse_int_field("defaultWindowTop")
        imported_window_width = _parse_int_field("defaultWindowWidth", min_value=1)
        imported_window_height = _parse_int_field("defaultWindowHeight", min_value=1)

        with self._state_lock:
            current_server_uuid = self._server_uuid
            current_window_left = self._default_window_left
            current_window_top = self._default_window_top
            current_window_width = self._default_window_width
            current_window_height = self._default_window_height
            # If not loading from file (e.g. push from Orchestrator), preserve existing overrides.
            current_overrides = dict(self._trigger_overrides)

        new_server_uuid: UUID
        if keepServerUuid:
            new_server_uuid = current_server_uuid
        else:
            server_uuid_raw = str(obj.get("serverUuid", "") or "").strip()
            parsed_uuid: Optional[UUID] = None
            try:
                if server_uuid_raw:
                    parsed_uuid = UUID(server_uuid_raw)
            except Exception:
                parsed_uuid = None
            new_server_uuid = parsed_uuid if parsed_uuid is not None else uuid4()

        # Load overrides from input if present (e.g. from local file)
        # If missing (e.g. from Orchestrator), we use current_overrides (if valid) or empty?
        # Actually, ImportStateDict is destructive for definitions.
        # If input has "triggerOverrides", use them. If not, preserve existing?
        # Scenario 1: Load local file -> has overrides -> use them.
        # Scenario 2: Push from Orchestrator -> no overrides -> preserve existing.
        loaded_overrides: Dict[UUID, bool] = {}
        overrides_any = obj.get("triggerOverrides", None)
        if overrides_any is not None and isinstance(overrides_any, dict):
            for k, v in cast(Dict[str, Any], overrides_any).items():
                try:
                    loaded_overrides[UUID(str(k))] = bool(v)
                except Exception:
                    pass
        else:
            # Preserve existing overrides if input didn't specify any (e.g. partial update or orchestrator push)
            loaded_overrides = current_overrides

        def decode_png_b64(b64: Optional[str]) -> Optional[Any]:
             return self._computer_vision.decode_image_from_b64(b64 or "")

        cond_list: Any = obj.get("conditions", [])
        act_list: Any = obj.get("actions", [])
        trig_list: Any = obj.get("triggers", [])

        loaded_conditions: Dict[UUID, ConditionItem] = {}
        if isinstance(cond_list, list):
            for c_any in cast(List[Any], cond_list):
                if not isinstance(c_any, dict):
                    continue
                c: Dict[str, Any] = cast(Dict[str, Any], c_any)
                try:
                    cu = UUID(str(c.get("uuid", "")))
                except Exception:
                    continue
                name = str(c.get("name", "") or "").strip()
                if not name:
                    continue
                type_name = str(c.get("type", "") or "").strip() or "ImageMatchRoi"
                try:
                    ctype = ConditionType[type_name]
                except Exception:
                    continue
                roi_obj = c.get("roi", {})
                if not isinstance(roi_obj, dict):
                    roi_obj = {}
                roi_obj_t: Dict[str, Any] = cast(Dict[str, Any], roi_obj)
                roi = ConditionRoi(
                    xNormalized=float(roi_obj_t.get("xNormalized", 0.0) or 0.0),
                    yNormalized=float(roi_obj_t.get("yNormalized", 0.0) or 0.0),
                    widthNormalized=float(roi_obj_t.get("widthNormalized", 0.0) or 0.0),
                    heightNormalized=float(roi_obj_t.get("heightNormalized", 0.0) or 0.0),
                )
                template = decode_png_b64(c.get("templateImageBase64", None))
                loaded_conditions[cu] = ConditionItem(
                    uuid=cu,
                    name=name,
                    roi=roi,
                    type=ctype,
                    templateImage=template,
                )

        loaded_actions: Dict[UUID, ActionItem] = {}
        if isinstance(act_list, list):
            for a_any in cast(List[Any], act_list):
                if not isinstance(a_any, dict):
                    continue
                a: Dict[str, Any] = cast(Dict[str, Any], a_any)
                try:
                    au = UUID(str(a.get("uuid", "")))
                except Exception:
                    continue
                name = str(a.get("name", "") or "").strip()
                if not name:
                    continue
                steps_in = a.get("steps", [])
                steps: List[MacroStep] = []
                if isinstance(steps_in, list):
                    for s_any in cast(List[Any], steps_in):
                        if not isinstance(s_any, dict):
                            continue
                        s: Dict[str, Any] = cast(Dict[str, Any], s_any)
                        action_name = str(s.get("action", "") or "").strip()
                        try:
                            st = MacroType[action_name]
                        except Exception:
                            continue
                        params = s.get("parameters", {})
                        if not isinstance(params, dict):
                            params = {}
                        steps.append(MacroStep(action=st, parameters=dict(cast(Dict[str, Any], params))))
                loaded_actions[au] = ActionItem(uuid=au, name=name, steps=steps)

        loaded_triggers: Dict[UUID, TriggerItem] = {}
        if isinstance(trig_list, list):
            for t_any in cast(List[Any], trig_list):
                if not isinstance(t_any, dict):
                    continue
                t: Dict[str, Any] = cast(Dict[str, Any], t_any)
                try:
                    tu = UUID(str(t.get("uuid", "")))
                except Exception:
                    continue
                name = str(t.get("name", "") or "").strip()
                if not name:
                    continue
                try:
                    action_uuid = UUID(str(t.get("action", "")))
                except Exception:
                    continue
                if action_uuid not in loaded_actions:
                    continue
                
                # Definition default
                default_enabled = bool(t.get("enabled", False))
                # Apply override if present
                final_enabled = loaded_overrides.get(tu, default_enabled)

                retrigger_ms = int(t.get("retriggerMs", 0) or 0)
                if retrigger_ms < 0:
                    retrigger_ms = 0
                disable_on_fire = bool(t.get("disableOnFire", False))

                crit_in = t.get("triggerCiterias", [])
                crit_out: List[TriggerCiteria] = []
                if isinstance(crit_in, list):
                    for c_any in cast(List[Any], crit_in):
                        if not isinstance(c_any, dict):
                            continue
                        c: Dict[str, Any] = cast(Dict[str, Any], c_any)
                        try:
                            cond_uuid = UUID(str(c.get("conditionUuid", "")))
                        except Exception:
                            continue
                        if cond_uuid not in loaded_conditions:
                            continue
                        comp_name = str(c.get("comparator", "") or "").strip()
                        try:
                            comp = TriggerComparator[comp_name]
                        except Exception:
                            continue
                        crit_out.append(TriggerCiteria(
                            conditionUuid=cond_uuid,
                            expectedValue=c.get("expectedValue", None),
                            comparator=comp,
                        ))

                mode_name = str(t.get("criteriaMode", "") or "").strip() or "All"
                try:
                    mode = TriggerCriteriaMode[mode_name]
                except Exception:
                    mode = TriggerCriteriaMode.All

                loaded_triggers[tu] = TriggerItem(
                    uuid=tu,
                    name=name,
                    triggerCiterias=crit_out,
                    action=action_uuid,
                    enabled=final_enabled,
                    retriggerMs=retrigger_ms,
                    disableOnFire=disable_on_fire,
                    criteriaMode=mode,
                )

        with self._state_lock:
            self._server_uuid = new_server_uuid

            # Restore persisted operator defaults.
            self._default_app_path = imported_default_app_path
            self._default_window_title = imported_default_window_title
            self._default_window_left = imported_window_left if imported_window_left is not None else current_window_left
            self._default_window_top = imported_window_top if imported_window_top is not None else current_window_top
            self._default_window_width = imported_window_width if imported_window_width is not None else current_window_width
            self._default_window_height = imported_window_height if imported_window_height is not None else current_window_height

            # Replace config state atomically.
            self._conditionItemList = dict(loaded_conditions)
            self._actionItemList = dict(loaded_actions)
            self._triggerItemList = dict(loaded_triggers)
            
            # Prune overrides for UUIDs that no longer exist in the definition list (cleanup orphans).
            self._trigger_overrides = {k: v for k, v in loaded_overrides.items() if k in loaded_triggers}

            # Reset runtime caches/counters.
            self._trigger_last_match.clear()
            self._trigger_fire_count.clear()
            self._trigger_last_fire_unix.clear()
            self._trigger_last_fire_mono.clear()
            self._trigger_last_eval.clear()
            self._trigger_status_seq += 1

    def LoadState(self, path: Union[str, Path]) -> None:
        p = Path(path)
        raw = p.read_text(encoding="utf-8")
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("state file must be a JSON object")
        obj: Dict[str, Any] = cast(Dict[str, Any], parsed)
        # When loading local state, we want to restore serverUuid.
        self.ImportStateDict(obj, keepServerUuid=False)

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

    def _trigger_keys_in_order(self) -> List[UUID]:
        return list(self._triggerItemList.keys())

    def _reorder_triggers_by_keys(self, keys: List[UUID]) -> None:
        self._triggerItemList = {k: self._triggerItemList[k] for k in keys}

    def UpsertTriggerItem(
        self,
        uuid: Optional[UUID],
        name: str,
        triggerCiterias: List[TriggerCiteria],
        action: UUID,
        enabled: bool = False,
        retriggerMs: int = 0,
        disableOnFire: bool = False,
        criteriaMode: TriggerCriteriaMode = TriggerCriteriaMode.All,
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
            
            # If inserting a new trigger (or updating), check for override
            final_enabled = bool(enabled)
            if trig_uuid in self._trigger_overrides:
                final_enabled = self._trigger_overrides[trig_uuid]

            item = TriggerItem(
                uuid=trig_uuid,
                name=clean_name,
                triggerCiterias=list(triggerCiterias or []),
                action=action,
                enabled=final_enabled,
                retriggerMs=retrigger_ms_int,
                disableOnFire=bool(disableOnFire),
                criteriaMode=criteriaMode,
            )
            self._triggerItemList[trig_uuid] = item
            return item

    def SetTriggerEnabled(self, uuid: UUID, enabled: bool) -> TriggerItem:
        with self._state_lock:
            existing = self._triggerItemList.get(uuid)
            if existing is None:
                raise KeyError("Trigger uuid not found")
            
            # Save override
            self._trigger_overrides[uuid] = bool(enabled)

            updated = TriggerItem(
                uuid=existing.uuid,
                name=existing.name,
                triggerCiterias=list(existing.triggerCiterias or []),
                action=existing.action,
                enabled=bool(enabled),
                retriggerMs=int(getattr(existing, "retriggerMs", 0) or 0),
                disableOnFire=bool(getattr(existing, "disableOnFire", False)),
                criteriaMode=getattr(existing, "criteriaMode", TriggerCriteriaMode.All),
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
            self._trigger_overrides.pop(uuid, None)
            self._trigger_last_match.pop(uuid, None)
            self._trigger_fire_count.pop(uuid, None)
            self._trigger_last_fire_unix.pop(uuid, None)
            self._trigger_last_fire_mono.pop(uuid, None)
            self._trigger_last_eval.pop(uuid, None)

    def MoveTriggerItemByUuid(self, uuid: UUID, direction: str) -> None:
        dir_norm = (direction or "").strip().lower()
        with self._state_lock:
            keys = self._trigger_keys_in_order()
            if uuid not in self._triggerItemList:
                raise KeyError("Trigger uuid not found")

            index = keys.index(uuid)
            n = len(keys)

            if dir_norm == "up":
                if index == 0:
                    return
                keys[index - 1], keys[index] = keys[index], keys[index - 1]
                self._reorder_triggers_by_keys(keys)
                return

            if dir_norm == "down":
                if index >= n - 1:
                    return
                keys[index + 1], keys[index] = keys[index], keys[index + 1]
                self._reorder_triggers_by_keys(keys)
                return

            raise ValueError("direction must be 'up' or 'down'")

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

    async def _trigger_worker(self) -> None:
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

        while self._running:
            interval = 0.2
            try:
                # Batch all state reads under one lock for reduced contention.
                with self._state_lock:
                    self._trigger_last_error = None
                    interval = float(self._trigger_interval_seconds)
                    triggers = list(self._triggerItemList.values())
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

                    mode = getattr(t, "criteriaMode", TriggerCriteriaMode.All)
                    mode_is_any = (mode == TriggerCriteriaMode.Any)
                    matched = False if mode_is_any else True
                    has_criteria = False
                    for c in (t.triggerCiterias or []):
                        has_criteria = True
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
                        if ok:
                            if mode_is_any:
                                matched = True
                        else:
                            if not mode_is_any:
                                matched = False
                                break

                    if mode_is_any and not has_criteria:
                        matched = False

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
                            await self.EnqueueRunActionByUuid(t.action)
                            now_unix = float(time.time())
                            now_mono = float(time.monotonic())
                            with self._state_lock:
                                self._trigger_fire_count[t.uuid] = int(self._trigger_fire_count.get(t.uuid, 0)) + 1
                                self._trigger_last_fire_unix[t.uuid] = now_unix
                                self._trigger_last_fire_mono[t.uuid] = now_mono
                            if bool(getattr(t, "disableOnFire", False)):
                                with self._state_lock:
                                    existing = self._triggerItemList.get(t.uuid)
                                    if existing is not None and bool(existing.enabled):
                                        self._triggerItemList[t.uuid] = TriggerItem(
                                            uuid=existing.uuid,
                                            name=existing.name,
                                            triggerCiterias=list(existing.triggerCiterias or []),
                                            action=existing.action,
                                            enabled=False,
                                            retriggerMs=int(getattr(existing, "retriggerMs", 0) or 0),
                                            disableOnFire=bool(getattr(existing, "disableOnFire", False)),
                                            criteriaMode=getattr(existing, "criteriaMode", TriggerCriteriaMode.All),
                                        )
                                        self._trigger_last_match[t.uuid] = False
                        except Exception as exc:
                            with self._state_lock:
                                self._trigger_last_error = exc

                with self._state_lock:
                    self._trigger_status_seq += 1

            except asyncio.CancelledError:
                break
            except BaseException as exc:
                with self._state_lock:
                    self._trigger_last_error = exc
            
            try:
                await asyncio.sleep(max(0.05, interval))
            except asyncio.CancelledError:
                break

    def GetActionItemByUuid(self, uuid: UUID) -> Optional[ActionItem]:
        with self._state_lock:
            return self._actionItemList.get(uuid)

    def _action_keys_in_order(self) -> List[UUID]:
        return list(self._actionItemList.keys())

    def _reorder_actions_by_keys(self, keys: List[UUID]) -> None:
        self._actionItemList = {k: self._actionItemList[k] for k in keys}

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
            self._action_run_count.pop(uuid, None)
            self._action_last_started_unix.pop(uuid, None)
            self._action_last_completed_unix.pop(uuid, None)

    def MoveActionItemByUuid(self, uuid: UUID, direction: str) -> None:
        dir_norm = (direction or "").strip().lower()
        with self._state_lock:
            keys = self._action_keys_in_order()
            if uuid not in self._actionItemList:
                raise KeyError("Action uuid not found")

            index = keys.index(uuid)
            n = len(keys)

            if dir_norm == "up":
                if index == 0:
                    return
                keys[index - 1], keys[index] = keys[index], keys[index - 1]
                self._reorder_actions_by_keys(keys)
                return

            if dir_norm == "down":
                if index >= n - 1:
                    return
                keys[index + 1], keys[index] = keys[index], keys[index + 1]
                self._reorder_actions_by_keys(keys)
                return

            raise ValueError("direction must be 'up' or 'down'")

    async def EnqueueRunActionByUuid(self, uuid: UUID) -> None:
        with self._state_lock:
            if uuid not in self._actionItemList:
                raise KeyError("Action uuid not found")
            self._macro_last_enqueued_action_uuid = uuid
            self._macro_last_enqueued_unix = float(time.time())

        try:
            self._macro_queue.put_nowait(uuid)
        except asyncio.QueueFull:
            # Drop oldest and enqueue newest.
            try:
                self._macro_queue.get_nowait()
                self._macro_queue.task_done()
            except asyncio.QueueEmpty:
                pass
            try:
                self._macro_queue.put_nowait(uuid)
            except asyncio.QueueFull:
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

    async def _macro_worker(self) -> None:
        while self._running:
            try:
                action_uuid = await self._macro_queue.get()
            except asyncio.CancelledError:
                break

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
                        # interruptible sleep
                        await asyncio.sleep(max(0.0, seconds))
            except asyncio.CancelledError:
                break
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
        templateImage: Optional[Any] = None,
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

    def _encode_thumb_b64(self, img: Any, maxSize: int = 64) -> Optional[str]:
        if img is None:
            return None
        # We need to get width/height.
        # Since we use numpy array as Image, we can check shape.
        # But to be clean we should probably expose "get_size" in interface,
        # or just assume numpy since Services uses numpy heavily.
        # Services.py is domain logic, but it's tied to numpy data structures.
        try:
            h, w = img.shape[:2]
        except AttributeError:
             return None

        if h <= 0 or w <= 0:
            return None

        scale = float(maxSize) / float(max(h, w))
        out = img
        if scale < 1.0:
            new_w = max(1, int(round(w * scale)))
            new_h = max(1, int(round(h * scale)))
            out = self._computer_vision.resize_image(img, new_w, new_h)

        return self._computer_vision.encode_image_to_b64(out)

    def _condition_status_worker(self) -> None:
        while self._running:
            # Batch state reads under one lock for reduced contention.
            with self._state_lock:
                interval = float(self._condition_status_interval_seconds)
                items = list(self._conditionItemList.values())
            if interval <= 0:
                interval = 0.5

            # Snapshot latest capture (read-only reference, no copy needed).
            with self._capture_lock:
                frame = self._latest_capture

            snapshots: List[ConditionStatusSnapshot] = []

            for item in items:
                template_thumb = self._encode_thumb_b64(item.templateImage) if item.templateImage is not None else None

                crop_thumb: Optional[str] = None
                last: Optional[float] = None

                if frame is not None:
                    try:
                        crop = self._computer_vision.crop_image(frame, item.roi.to_tuple())
                        crop_thumb = self._encode_thumb_b64(crop)

                        if item.type == ConditionType.ImageMatchRoi:
                            if item.templateImage is not None:
                                last = float(self._computer_vision.match_template(crop, item.templateImage))
                        elif item.type == ConditionType.ProgressBar:
                            last = float(self._computer_vision.estimate_progress_bar(crop))
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

            if self._shutdown_event.wait(interval):
                break

    def LaunchApp(self, app_path: str, left: int = 0, top: int = 0, width: int = 640, height: int = 480) -> None:
        with self._state_lock:
            self._default_app_path = str(app_path or "").strip()
            self._default_window_left = int(left)
            self._default_window_top = int(top)
            if int(width) > 0:
                self._default_window_width = int(width)
            if int(height) > 0:
                self._default_window_height = int(height)
        self._launch_app_internal(app_path, left=left, top=top, width=width, height=height)

    def _launch_app_internal(self, app_path: str, left: int = 0, top: int = 0, width: int = 640, height: int = 480) -> None:
        self._pid = int(self._window_manager.launch_process(app_path))
        foundHwnd = self._window_manager.find_window_by_pid(self._pid)
        if foundHwnd is None:
            raise Exception("Failed to find window handle for launched application.")
        with self._state_lock:
            self._hwnd = foundHwnd

        if width <= 0 or height <= 0:
            raise ValueError("width and height must be > 0")
        self._window_manager.move_and_resize_window(self._hwnd, int(left), int(top), int(width), int(height))

    def AttachApp(self, window_title: str, left: int = 0, top: int = 0, width: int = 640, height: int = 480) -> None:
        with self._state_lock:
            self._default_window_title = str(window_title or "").strip()
            self._default_window_left = int(left)
            self._default_window_top = int(top)
            if int(width) > 0:
                self._default_window_width = int(width)
            if int(height) > 0:
                self._default_window_height = int(height)
        foundHwnd = self._window_manager.find_window_by_title(window_title)
        if foundHwnd is None:
            raise Exception("Failed to find window handle for the specified title.")
        with self._state_lock:
            self._hwnd = foundHwnd
            self._pid = self._window_manager.find_pid_by_window(self._hwnd)

        if width <= 0 or height <= 0:
            raise ValueError("width and height must be > 0")
        self._window_manager.move_and_resize_window(self._hwnd, int(left), int(top), int(width), int(height))

    def CloseApp(self) -> None:
        # Ensure any capture loop is stopped before tearing down the window/process.
        self.StopCapture()
        pidToKill = 0
        with self._state_lock:
            pidToKill = self._pid
            self._pid = 0
            self._hwnd = 0

        if pidToKill != 0:
            self._window_manager.terminate_process(pidToKill)

        # Drain any queued control actions for the closed app.
        try:
            while True:
                self._control_queue.get_nowait()
                self._control_queue.task_done()
        except asyncio.QueueEmpty:
            pass

    def DetachApp(self) -> None:
        """Detach from the currently attached window without killing the process."""
        # Stop capture and clear attached handles, but do not terminate the process.
        self.StopCapture()
        with self._state_lock:
            self._pid = 0
            self._hwnd = 0

        # Drain any queued control actions for the detached app.
        try:
            while True:
                self._control_queue.get_nowait()
                self._control_queue.task_done()
        except asyncio.QueueEmpty:
            pass

    def FocusApp(self, window_title: Optional[str] = None) -> None:
        target_title = str(window_title or "").strip()
        hwnd = 0

        if target_title:
            found = self._window_manager.find_window_by_title(target_title)
            if found is None:
                raise Exception("Failed to find window handle for the specified title.")
            hwnd = found
        else:
            with self._state_lock:
                hwnd = self._hwnd
                target_title = str(self._default_window_title or "").strip()

            if hwnd == 0 and target_title:
                found = self._window_manager.find_window_by_title(target_title)
                if found is None:
                    raise Exception("Failed to find window handle for the default title.")
                hwnd = found

        if hwnd == 0:
            raise Exception("No application is attached for focus.")

        self._window_manager.focus_window(hwnd)

        with self._state_lock:
            self._hwnd = hwnd
            if hwnd:
                try:
                    self._pid = self._window_manager.find_pid_by_window(hwnd)
                except Exception:
                    pass

    def ResizeApp(self, left: int = 0, top: int = 0, width: int = 640, height: int = 480) -> None:
        if int(width) <= 0 or int(height) <= 0:
            raise ValueError("width and height must be > 0")

        hwnd = 0
        default_title = ""
        with self._state_lock:
            hwnd = self._hwnd
            default_title = str(self._default_window_title or "").strip()

        if hwnd == 0 and default_title:
            found = self._window_manager.find_window_by_title(default_title)
            if found is None:
                raise Exception("Failed to find window handle for the default title.")
            hwnd = found

        if hwnd == 0:
            raise Exception("No application is attached for resize.")

        self._window_manager.move_and_resize_window(hwnd, int(left), int(top), int(width), int(height))

        with self._state_lock:
            self._hwnd = hwnd
            self._default_window_left = int(left)
            self._default_window_top = int(top)
            self._default_window_width = int(width)
            self._default_window_height = int(height)
            try:
                self._pid = self._window_manager.find_pid_by_window(hwnd)
            except Exception:
                pass

    async def _control_worker(self) -> None:
        while self._running:
            try:
                action = await self._control_queue.get()
            except asyncio.CancelledError:
                break

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
        while self._running:
            self._capture_enabled_event.wait(timeout=0.5)
            if not self._running:
                break

            while self._capture_enabled_event.is_set() and self._running:
                with self._state_lock:
                    hwnd = self._hwnd
                    interval = float(self._capture_interval_seconds)

                if interval <= 0:
                    interval = 1.0

                if hwnd == 0:
                    with self._capture_lock:
                        self._capture_last_error = Exception("No application is attached for capturing.")
                    
                    if self._shutdown_event.wait(interval):
                        break
                    continue

                try:
                    frame = self._screen_capturer.capture_window(hwnd)
                    with self._capture_lock:
                        self._latest_capture = frame
                        self._capture_last_error = None
                        self._capture_seq += 1
                except BaseException as exc:
                    with self._capture_lock:
                        self._capture_last_error = exc

                if self._shutdown_event.wait(interval):
                    break

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

    def Shutdown(self) -> None:
        # Backward compatibility for sync callers, though Start/Stop are async now.
        # Ideally, main.py calls Stop() which awaits.
        self._running = False
        self._shutdown_event.set()
        self._capture_enabled_event.set()

    def IsRunning(self) -> bool:
        return self._running

    def WaitShutdown(self, timeout: float) -> bool:
        """Wait for shutdown signal with timeout. Returns True if shutting down."""
        return self._shutdown_event.wait(timeout)

    def GetLatestCapture(self) -> Optional[NDArray[np.uint8]]:
        """Return the latest captured frame (read-only; do not mutate)."""
        with self._capture_lock:
            return self._latest_capture

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

        self._input_controller.click(hwnd, x, y)

    async def EnqueueClick(self, normalizedX: float, normalizedY: float) -> None:
        action = _ControlAction(kind="click", x=float(normalizedX), y=float(normalizedY))
        try:
            self._control_queue.put_nowait(action)
        except asyncio.QueueFull:
            # KISS stability: drop oldest action and enqueue newest.
            try:
                self._control_queue.get_nowait()
                self._control_queue.task_done()
            except asyncio.QueueEmpty:
                pass
            try:
                self._control_queue.put_nowait(action)
            except asyncio.QueueFull:
                pass

    def _execute_key(self, keyName: str) -> None:
        name = (keyName or "").strip()
        if not name:
            raise ValueError("keyName cannot be empty")

        with self._state_lock:
            hwnd = self._hwnd

        if hwnd == 0:
            raise Exception("No application is attached for control.")

        self._input_controller.press_key(hwnd, name)

    async def EnqueueKeyStroke(self, keyName: str) -> None:
        action = _ControlAction(kind="key", x=0.0, y=0.0, key=str(keyName))
        try:
            self._control_queue.put_nowait(action)
        except asyncio.QueueFull:
            # Same policy: drop oldest and keep newest.
            try:
                self._control_queue.get_nowait()
                self._control_queue.task_done()
            except asyncio.QueueEmpty:
                pass
            try:
                self._control_queue.put_nowait(action)
            except asyncio.QueueFull:
                pass

    def GetLastControlError(self) -> Optional[BaseException]:
        with self._state_lock:
            return self._control_last_error
