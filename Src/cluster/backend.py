from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.responses import Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import sys
import os
import time
import asyncio
from pathlib import Path
from enum import Enum
import base64
import json
from uuid import UUID

import cv2
import numpy as np
from numpy.typing import NDArray

from typing import List, Optional, Any, Dict, cast

from .services import ControllerServices

app = FastAPI()
services: Optional[ControllerServices] = None


def _state_root() -> Path:
    """Where to store persistent state.

    Policy:
    - In dev: project root
    - In packaged exe: prefer the EXE folder *if writable*, otherwise fall back to a per-user folder

    You can override the directory with `SENTINELFLOW_STATE_DIR`.
    """

    def is_writable_dir(p: Path) -> bool:
        try:
            p.mkdir(parents=True, exist_ok=True)
            probe = p / ".sentinelflow_write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return True
        except Exception:
            return False

    if bool(getattr(sys, "frozen", False)):
        override = (os.getenv("SENTINELFLOW_STATE_DIR") or "").strip()
        candidates: List[Path] = []
        if override:
            candidates.append(Path(override))

        try:
            candidates.append(Path(sys.executable).resolve().parent)
        except Exception:
            candidates.append(Path.cwd())

        appdata = (os.getenv("LOCALAPPDATA") or os.getenv("APPDATA") or "").strip()
        if appdata:
            candidates.append(Path(appdata) / "SentinelFlow")

        candidates.append(Path.home() / ".sentinelflow")

        for c in candidates:
            if is_writable_dir(c):
                return c

        # Last resort.
        return Path.cwd()

    return Path(__file__).resolve().parents[2]


_STATE_PATH = _state_root() / "state.json"


def _candidate_state_paths() -> List[Path]:
    """Possible locations for reading state.

    `_STATE_PATH` is the primary write location; this list also includes
    legacy/alternate locations so packaged builds can find existing state.
    """
    paths: List[Path] = [_STATE_PATH]

    if bool(getattr(sys, "frozen", False)):
        # Also try the EXE folder explicitly (even if we fell back due to permissions).
        try:
            exe_dir = Path(sys.executable).resolve().parent
            exe_path = exe_dir / "state.json"
            if exe_path not in paths:
                paths.append(exe_path)
        except Exception:
            pass

    # In dev, also try CWD as a convenience.
    try:
        cwd_path = Path.cwd() / "state.json"
        if cwd_path not in paths:
            paths.append(cwd_path)
    except Exception:
        pass

    return paths


def _find_existing_state_path() -> Optional[Path]:
    for p in _candidate_state_paths():
        try:
            if p.exists():
                return p
        except Exception:
            continue
    return None


def _try_load_state(svc: ControllerServices) -> None:
    try:
        existing = _find_existing_state_path()
        if existing is None:
            return

        svc.LoadState(existing)

        # If we loaded from a non-primary location, migrate by saving to the primary.
        if existing != _STATE_PATH:
            try:
                svc.SaveState(_STATE_PATH)
                print(f"[state] Migrated state.json from {existing} -> {_STATE_PATH}")
            except Exception as exc:
                print(f"[state] Migration save failed: {exc}")
    except FileNotFoundError:
        return
    except Exception as exc:
        # Don't block startup on corrupted state; operator can delete state.json.
        print(f"[state] Load failed: {exc}")


def _ensure_state_file(svc: ControllerServices) -> None:
    """Ensure `state.json` exists so serverUuid/defaults persist even without edits."""
    try:
        if not _STATE_PATH.exists():
            svc.SaveState(_STATE_PATH)
            print(f"[state] Initialized new state at {_STATE_PATH}")
    except Exception as exc:
        print(f"[state] Init save failed: {exc}")


def _try_save_state(svc: ControllerServices) -> None:
    try:
        svc.SaveState(_STATE_PATH)
    except Exception as exc:
        print(f"[state] Save failed: {exc}")

def _resource_root() -> Path:
    """Return the runtime root directory.

    - In development: project root (the folder containing `Src/` and `web/`).
    - In PyInstaller onefile: the extraction directory (`sys._MEIPASS`).
    """
    mei_root = getattr(sys, "_MEIPASS", None)
    if mei_root:
        return Path(mei_root)
    return Path(__file__).resolve().parents[2]


_public_dir = _resource_root() / "web" / "cluster"
app.mount("/static", StaticFiles(directory=str(_public_dir)), name="static")


def _get_services() -> ControllerServices:
    # Prefer an instance wired by the entrypoint (cluster main), but fall back
    # to the module-level instance for backwards compatibility.
    svc = getattr(app.state, "services", None)
    if svc is not None:
        if not bool(getattr(app.state, "stateLoaded", False)):
            _try_load_state(svc)
            _ensure_state_file(svc)
            app.state.stateLoaded = True
        return svc

    global services
    if services is None:
        services = ControllerServices()
        _try_load_state(services)
        _ensure_state_file(services)
    return services


@app.get("/api/server/info")
def GetServerInfo() -> Dict[str, Any]:
    svc = _get_services()
    return {
        "serverUuid": str(svc.GetServerUuid()),
    }


@app.get("/api/state/export")
def ExportState(includeServerUuid: bool = False) -> Dict[str, Any]:
    svc = _get_services()
    return svc.ExportStateDict(includeServerUuid=bool(includeServerUuid))


@app.get("/api/state/path")
def GetStatePath() -> Dict[str, Any]:
    """Return the resolved path where this node reads/writes `state.json`."""
    return {"path": str(_STATE_PATH)}


class StateImportRequest(BaseModel):
    state: Dict[str, Any]
    keepServerUuid: bool = True


@app.post("/api/state/import")
def ImportState(req: StateImportRequest) -> Dict[str, Any]:
    svc = _get_services()
    try:
        svc.ImportStateDict(dict(req.state), keepServerUuid=bool(req.keepServerUuid))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Import failed: {exc}")

    _try_save_state(svc)
    return {"ok": True}


@app.post("/api/state/reload")
def ReloadState() -> Dict[str, Any]:
    svc = _get_services()
    try:
        svc.LoadState(_STATE_PATH)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="state.json not found")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Reload failed: {exc}")

    # Mark loaded for app.state-backed services.
    try:
        app.state.stateLoaded = True
    except Exception:
        pass

    return {"ok": True, "serverUuid": str(svc.GetServerUuid())}


@app.get("/api/app/defaults")
def GetAppDefaults() -> Dict[str, Any]:
    svc = _get_services()
    return svc.GetAppDefaults()


class AppDefaultsUpdateRequest(BaseModel):
    defaultAppPath: Optional[str] = None
    defaultWindowTitle: Optional[str] = None
    defaultWindowLeft: Optional[int] = None
    defaultWindowTop: Optional[int] = None
    defaultWindowWidth: Optional[int] = None
    defaultWindowHeight: Optional[int] = None
    app_path: Optional[str] = None
    window_title: Optional[str] = None
    left: Optional[int] = None
    top: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None


@app.post("/api/app/defaults")
def SetAppDefaults(req: AppDefaultsUpdateRequest) -> Dict[str, Any]:
    svc = _get_services()
    app_path = req.defaultAppPath if req.defaultAppPath is not None else req.app_path
    window_title = req.defaultWindowTitle if req.defaultWindowTitle is not None else req.window_title
    left = req.defaultWindowLeft if req.defaultWindowLeft is not None else req.left
    top = req.defaultWindowTop if req.defaultWindowTop is not None else req.top
    width = req.defaultWindowWidth if req.defaultWindowWidth is not None else req.width
    height = req.defaultWindowHeight if req.defaultWindowHeight is not None else req.height
    if (
        app_path is None
        and window_title is None
        and left is None
        and top is None
        and width is None
        and height is None
    ):
        raise HTTPException(status_code=400, detail="No defaults provided")

    defaults = svc.SetAppDefaults(
        default_app_path=app_path,
        default_window_title=window_title,
        default_window_left=left,
        default_window_top=top,
        default_window_width=width,
        default_window_height=height,
    )
    _try_save_state(svc)
    return {"ok": True, **defaults}


class LaunchRequest(BaseModel):
    app_path: str
    left: int = 0
    top: int = 0
    width: int = 640
    height: int = 480


class AttachRequest(BaseModel):
    window_title: str
    left: int = 0
    top: int = 0
    width: int = 640
    height: int = 480


class FocusRequest(BaseModel):
    window_title: Optional[str] = None


class ResizeRequest(BaseModel):
    left: int = 0
    top: int = 0
    width: int = 640
    height: int = 480


class CaptureStartRequest(BaseModel):
    intervalSeconds: float = 1.0


class ClickRequest(BaseModel):
    x: float
    y: float


class KeyRequest(BaseModel):
    keyName: str


class MacroTypeDto(str, Enum):
    Click = "Click"
    KeyStroke = "KeyStroke"
    Delay = "Delay"


class MacroStepDto(BaseModel):
    action: MacroTypeDto
    parameters: Dict[str, Any] = {}


class ActionItemDto(BaseModel):
    uuid: str
    name: str
    steps: List[MacroStepDto]


class ActionUpsertRequest(BaseModel):
    uuid: Optional[UUID] = None
    name: str
    steps: List[MacroStepDto] = []


class ActionUuidRequest(BaseModel):
    uuid: UUID


class ActionMoveRequest(BaseModel):
    uuid: UUID
    direction: str  # 'up' | 'down'


class TriggerComparatorDto(str, Enum):
    Equals = "Equals"
    NotEquals = "NotEquals"
    GreaterThan = "GreaterThan"
    LessThan = "LessThan"
    GreaterThanOrEqual = "GreaterThanOrEqual"
    LessThanOrEqual = "LessThanOrEqual"

class TriggerCriteriaModeDto(str, Enum):
    All = "All"
    Any = "Any"


class TriggerCiteriaDto(BaseModel):
    conditionUuid: UUID
    expectedValue: Any
    comparator: TriggerComparatorDto


class TriggerItemDto(BaseModel):
    uuid: str
    name: str
    enabled: bool = False
    retriggerMs: int = 0
    triggerCiterias: List[TriggerCiteriaDto] = []
    criteriaMode: TriggerCriteriaModeDto = TriggerCriteriaModeDto.All
    action: str


class TriggerUpsertRequest(BaseModel):
    uuid: Optional[UUID] = None
    name: str
    enabled: bool = False
    retriggerMs: int = 0
    triggerCiterias: List[TriggerCiteriaDto] = []
    criteriaMode: Optional[TriggerCriteriaModeDto] = None
    action: UUID


class TriggerUuidRequest(BaseModel):
    uuid: UUID


class TriggerMoveRequest(BaseModel):
    uuid: UUID
    direction: str  # 'up' | 'down'


class TriggerSetEnabledRequest(BaseModel):
    uuid: UUID
    enabled: bool


class ConditionTypeDto(str, Enum):
    ImageMatchRoi = "ImageMatchRoi"
    ProgressBar = "ProgressBar"


class ConditionRoiDto(BaseModel):
    xNormalized: float
    yNormalized: float
    widthNormalized: float
    heightNormalized: float


class ConditionItemDto(BaseModel):
    uuid: str
    name: str
    type: ConditionTypeDto
    roi: ConditionRoiDto


class ConditionStatusDto(BaseModel):
    uuid: str
    index: Optional[int] = None
    name: str
    type: ConditionTypeDto
    templateThumbBase64: Optional[str] = None
    cropThumbBase64: Optional[str] = None
    last: Optional[float] = None

class ConditionUuidRequest(BaseModel):
    uuid: UUID


class ConditionMoveRequest(BaseModel):
    uuid: UUID
    direction: str  # 'up' | 'down'


class ConditionSetFromLiveRequest(BaseModel):
    uuid: UUID
    roi: ConditionRoiDto
    name: Optional[str] = None
    type: Optional[ConditionTypeDto] = None
    templateImageBase64: Optional[str] = None
    templateFromLive: bool = True


class ConditionUpsertRequest(BaseModel):
    name: str
    type: ConditionTypeDto
    roi: ConditionRoiDto
    templateImageBase64: Optional[str] = None
    templateFromLive: bool = False


def _crop_frame_normalized(frame: NDArray[np.uint8], roi: ConditionRoiDto) -> NDArray[np.uint8]:
    h, w = frame.shape[:2]

    x = float(max(0.0, min(1.0, roi.xNormalized)))
    y = float(max(0.0, min(1.0, roi.yNormalized)))
    rw = float(max(0.0, min(1.0, roi.widthNormalized)))
    rh = float(max(0.0, min(1.0, roi.heightNormalized)))

    px = int(x * w)
    py = int(y * h)
    pw = int(rw * w)
    ph = int(rh * h)

    px = max(0, min(px, w - 1))
    py = max(0, min(py, h - 1))
    pw = max(1, min(pw, w - px))
    ph = max(1, min(ph, h - py))

    return frame[py : py + ph, px : px + pw].copy()


# Serve the HTML file from the cluster UI directory
@app.get("/", response_class=FileResponse)
def ServeIndex():
    index_path = _public_dir / "index.html"
    return FileResponse(str(index_path), media_type="text/html")


@app.post("/api/app/launch")
def LaunchApp(req: LaunchRequest):
    svc = _get_services()
    svc.LaunchApp(req.app_path, left=req.left, top=req.top, width=req.width, height=req.height)
    _try_save_state(svc)
    return {"ok": True}


@app.post("/api/app/attach")
def AttachApp(req: AttachRequest):
    svc = _get_services()
    svc.AttachApp(req.window_title, left=req.left, top=req.top, width=req.width, height=req.height)
    _try_save_state(svc)
    return {"ok": True}


@app.post("/api/app/close")
def CloseApp():
    svc = _get_services()
    svc.CloseApp()
    return {"ok": True}


@app.post("/api/app/focus")
def FocusApp(req: FocusRequest) -> Dict[str, Any]:
    svc = _get_services()
    try:
        svc.FocusApp(window_title=req.window_title)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True}


@app.post("/api/app/resize")
def ResizeApp(req: ResizeRequest) -> Dict[str, Any]:
    svc = _get_services()
    try:
        svc.ResizeApp(left=req.left, top=req.top, width=req.width, height=req.height)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    _try_save_state(svc)
    return {"ok": True}


@app.post("/api/capture/start")
def StartCapture(req: CaptureStartRequest):
    svc = _get_services()
    svc.StartCapture(intervalSeconds=req.intervalSeconds)
    return {"ok": True}


@app.post("/api/capture/stop")
def StopCapture():
    svc = _get_services()
    svc.StopCapture()
    return {"ok": True}


@app.get("/api/capture/latest")
def GetLatestCapture(fmt: str = "png"):
    svc = _get_services()
    frame = svc.GetLatestCapture()
    if frame is None:
        lastErr = svc.GetLastCaptureError()
        detail = "No captured frame available. Call /api/capture/start first."
        if lastErr is not None:
            detail = f"{detail} Last capture error: {lastErr}"
        raise HTTPException(status_code=404, detail=detail)

    normalized = (fmt or "png").lower().strip(".")
    if normalized in ("jpg", "jpeg"):
        ext = ".jpg"
        media = "image/jpeg"
    elif normalized == "png":
        ext = ".png"
        media = "image/png"
    else:
        raise HTTPException(status_code=400, detail="fmt must be 'png' or 'jpg'")

    ok, encoded = cv2.imencode(ext, frame)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to encode captured frame")

    return Response(content=encoded.tobytes(), media_type=media)


@app.get("/api/capture/events")
async def CaptureEvents(request: Request):
    svc = _get_services()

    async def event_stream():
        # Send an initial retry hint to the browser.
        yield "retry: 1000\n\n"

        last_seq = svc.GetCaptureSequence()
        last_keepalive = time.monotonic()

        while True:
            if await request.is_disconnected():
                break

            seq = svc.GetCaptureSequence()
            if seq != last_seq and seq > 0:
                last_seq = seq
                yield f"event: frame\ndata: {seq}\n\n"

            now = time.monotonic()
            if now - last_keepalive >= 10.0:
                # Comment line as keepalive.
                yield ": keepalive\n\n"
                last_keepalive = now

            await asyncio.sleep(0.2)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/api/capture/stream")
async def CaptureStream(request: Request, fmt: str = "jpg", quality: int = 70):
    """Stream captured frames over SSE as base64-encoded image payloads.

    This avoids a second HTTP request per frame (no /api/capture/latest polling).
    """
    svc = _get_services()

    normalized = (fmt or "jpg").lower().strip(".")
    if normalized not in ("jpg", "jpeg"):
        raise HTTPException(status_code=400, detail="fmt must be 'jpg'")

    q = int(quality)
    q = max(10, min(95, q))

    async def event_stream():
        yield "retry: 1000\n\n"

        last_seq = svc.GetCaptureSequence()
        last_keepalive = time.monotonic()

        while True:
            if await request.is_disconnected():
                break

            seq = svc.GetCaptureSequence()
            if seq != last_seq and seq > 0:
                last_seq = seq
                frame = svc.GetLatestCapture()
                if frame is not None:
                    ok, encoded = cv2.imencode(
                        ".jpg",
                        frame,
                        [int(cv2.IMWRITE_JPEG_QUALITY), q],
                    )
                    if ok:
                        b64 = base64.b64encode(encoded.tobytes()).decode("ascii")
                        yield f"event: frame\ndata: {b64}\n\n"

            now = time.monotonic()
            if now - last_keepalive >= 10.0:
                yield ": keepalive\n\n"
                last_keepalive = now

            await asyncio.sleep(0.2)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/api/control/click")
def ControlClick(req: ClickRequest):
    svc = _get_services()
    svc.EnqueueClick(req.x, req.y)
    return {"ok": True}


@app.post("/api/control/key")
def ControlKey(req: KeyRequest):
    svc = _get_services()
    svc.EnqueueKeyStroke(req.keyName)
    return {"ok": True}


@app.get("/api/actions")
def GetActions() -> List[ActionItemDto]:
    svc = _get_services()
    out: List[ActionItemDto] = []
    for item in svc.GetActionItems():
        steps: List[MacroStepDto] = []
        for s in item.steps:
            # Best-effort: map MacroType enum to string value.
            action_name = s.action.name
            steps.append(MacroStepDto(action=MacroTypeDto[action_name], parameters=dict(s.parameters)))

        out.append(ActionItemDto(uuid=str(item.uuid), name=item.name, steps=steps))
    return out


@app.get("/api/triggers")
def GetTriggers() -> List[TriggerItemDto]:
    svc = _get_services()
    out: List[TriggerItemDto] = []
    for t in svc.GetTriggerItems():
        citerias: List[TriggerCiteriaDto] = []
        for c in t.triggerCiterias or []:
            citerias.append(
                TriggerCiteriaDto(
                    conditionUuid=c.conditionUuid,
                    expectedValue=c.expectedValue,
                    comparator=TriggerComparatorDto[c.comparator.name],
                )
            )

        mode = getattr(t, "criteriaMode", None)
        mode_name = mode.name if mode is not None else "All"

        out.append(
            TriggerItemDto(
                uuid=str(t.uuid),
                name=t.name,
                enabled=bool(getattr(t, "enabled", False)),
                retriggerMs=int(getattr(t, "retriggerMs", 0) or 0),
                triggerCiterias=citerias,
                criteriaMode=TriggerCriteriaModeDto[mode_name],
                action=str(t.action),
            )
        )

    return out


@app.post("/api/triggers/upsert")
def UpsertTrigger(req: TriggerUpsertRequest) -> Dict[str, Any]:
    svc = _get_services()
    from .services import TriggerComparator, TriggerCiteria, TriggerCriteriaMode

    name = (req.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name cannot be empty")

    citerias: List[TriggerCiteria] = []
    for c in req.triggerCiterias or []:
        try:
            citerias.append(
                TriggerCiteria(
                    conditionUuid=c.conditionUuid,
                    expectedValue=c.expectedValue,
                    comparator=TriggerComparator[c.comparator.value],
                )
            )
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Invalid comparator: {c.comparator}")

    mode = TriggerCriteriaMode.All
    if req.criteriaMode is not None:
        try:
            mode = TriggerCriteriaMode[req.criteriaMode.value]
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Invalid criteriaMode: {req.criteriaMode}")

    try:
        item = svc.UpsertTriggerItem(
            req.uuid,
            name=name,
            triggerCiterias=citerias,
            action=req.action,
            enabled=bool(req.enabled),
            retriggerMs=int(getattr(req, "retriggerMs", 0) or 0),
            criteriaMode=mode,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except KeyError as exc:
        # Could be missing action or condition UUID.
        raise HTTPException(status_code=404, detail=str(exc))

    _try_save_state(svc)
    return {"ok": True, "uuid": str(item.uuid)}


@app.post("/api/triggers/remove_uuid")
def RemoveTriggerByUuid(req: TriggerUuidRequest) -> Dict[str, Any]:
    svc = _get_services()
    try:
        svc.RemoveTriggerItemByUuid(req.uuid)
    except KeyError:
        raise HTTPException(status_code=404, detail="Trigger uuid not found")
    _try_save_state(svc)
    return {"ok": True}


@app.post("/api/triggers/move")
def MoveTrigger(req: TriggerMoveRequest) -> Dict[str, Any]:
    svc = _get_services()
    try:
        svc.MoveTriggerItemByUuid(req.uuid, str(req.direction))
    except KeyError:
        raise HTTPException(status_code=404, detail="Trigger uuid not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    _try_save_state(svc)
    return {"ok": True}


@app.post("/api/triggers/set_enabled")
def SetTriggerEnabled(req: TriggerSetEnabledRequest) -> Dict[str, Any]:
    svc = _get_services()
    try:
        item = svc.SetTriggerEnabled(req.uuid, bool(req.enabled))
    except KeyError:
        raise HTTPException(status_code=404, detail="Trigger uuid not found")
    _try_save_state(svc)
    return {"ok": True, "uuid": str(item.uuid), "enabled": bool(item.enabled)}


@app.get("/api/triggers/status")
def GetTriggerStatus() -> Dict[str, Any]:
    svc = _get_services()
    return {
        "items": svc.GetTriggerStatusSnapshot(),
        "lastError": (repr(svc.GetLastTriggerError()) if svc.GetLastTriggerError() is not None else None),
        "macro": svc.GetMacroState(),
    }


@app.get("/api/triggers/status/stream")
async def TriggerStatusStream(request: Request):
    svc = _get_services()

    async def event_stream():
        yield "retry: 1000\n\n"

        last_seq = svc.GetTriggerStatusSequence()
        last_keepalive = time.monotonic()

        while True:
            if await request.is_disconnected():
                break

            seq = svc.GetTriggerStatusSequence()
            if seq != last_seq:
                last_seq = seq
                payload: Dict[str, Any] = {
                    "seq": int(seq),
                    "items": svc.GetTriggerStatusSnapshot(),
                    "lastError": (repr(svc.GetLastTriggerError()) if svc.GetLastTriggerError() is not None else None),
                    "macro": svc.GetMacroState(),
                }
                yield f"event: status\ndata: {json.dumps(payload)}\n\n"

            now = time.monotonic()
            if now - last_keepalive >= 10.0:
                yield ": keepalive\n\n"
                last_keepalive = now

            await asyncio.sleep(0.2)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/api/triggers/debug")
def GetTriggerDebug() -> Dict[str, Any]:
    svc = _get_services()

    last_err = svc.GetLastTriggerError()
    last_match = svc.GetTriggerLastMatchDict()
    fire_count = svc.GetTriggerFireCountDict()
    last_fire = svc.GetTriggerLastFireUnixDict()

    return {
        "lastError": (repr(last_err) if last_err is not None else None),
        "lastMatchByUuid": {str(k): bool(v) for k, v in (last_match or {}).items()},
        "fireCountByUuid": {str(k): int(v) for k, v in (fire_count or {}).items()},
        "lastFireUnixByUuid": {str(k): float(v) for k, v in (last_fire or {}).items()},
    }


@app.post("/api/actions/upsert")
def UpsertAction(req: ActionUpsertRequest) -> Dict[str, Any]:
    svc = _get_services()
    from .services import MacroType, MacroStep

    name = (req.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name cannot be empty")

    steps: List[MacroStep] = []
    for s in req.steps or []:
        try:
            steps.append(MacroStep(action=MacroType[s.action.value], parameters=dict(s.parameters or {})))
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Invalid step action: {s.action}")

    try:
        item = svc.UpsertActionItem(req.uuid, name=name, steps=steps)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    _try_save_state(svc)
    return {"ok": True, "uuid": str(item.uuid)}


@app.post("/api/actions/remove_uuid")
def RemoveActionByUuid(req: ActionUuidRequest) -> Dict[str, Any]:
    svc = _get_services()
    try:
        svc.RemoveActionItemByUuid(req.uuid)
    except KeyError:
        raise HTTPException(status_code=404, detail="Action uuid not found")
    _try_save_state(svc)
    return {"ok": True}


@app.post("/api/actions/move")
def MoveAction(req: ActionMoveRequest) -> Dict[str, Any]:
    svc = _get_services()
    try:
        svc.MoveActionItemByUuid(req.uuid, str(req.direction))
    except KeyError:
        raise HTTPException(status_code=404, detail="Action uuid not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    _try_save_state(svc)
    return {"ok": True}


@app.post("/api/actions/run")
def RunAction(req: ActionUuidRequest) -> Dict[str, Any]:
    svc = _get_services()
    try:
        svc.EnqueueRunActionByUuid(req.uuid)
    except KeyError:
        raise HTTPException(status_code=404, detail="Action uuid not found")
    return {"ok": True}


@app.get("/api/actions/debug")
def GetActionDebug() -> Dict[str, Any]:
    svc = _get_services()
    last_err = svc.GetLastMacroError()
    return {
        "lastError": (repr(last_err) if last_err is not None else None),
        "macroQueueSize": int(svc.GetMacroQueueSize()),
    }


@app.get("/api/conditions")
def GetConditions() -> List[ConditionItemDto]:
    svc = _get_services()
    items: List[ConditionItemDto] = []
    for item in svc.GetConditionItems():
        items.append(
            ConditionItemDto(
                uuid=str(item.uuid),
                name=item.name,
                type=ConditionTypeDto[item.type.name],
                roi=ConditionRoiDto(
                    xNormalized=float(item.roi.xNormalized),
                    yNormalized=float(item.roi.yNormalized),
                    widthNormalized=float(item.roi.widthNormalized),
                    heightNormalized=float(item.roi.heightNormalized),
                ),
            )
        )
    return items


@app.post("/api/conditions")
def AddCondition(req: ConditionUpsertRequest) -> Dict[str, Any]:
    svc = _get_services()

    name = (req.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name cannot be empty")

    if req.roi.widthNormalized <= 0 or req.roi.heightNormalized <= 0:
        raise HTTPException(status_code=400, detail="roi width/height must be > 0")

    from .services import ConditionRoi, ConditionType

    template: Optional[NDArray[np.uint8]] = None
    raw_b64 = (req.templateImageBase64 or "").strip()
    if raw_b64:
        # Support both raw base64 and data URLs (data:image/png;base64,...)
        if "," in raw_b64:
            raw_b64 = raw_b64.split(",", 1)[1]
        try:
            binary = base64.b64decode(raw_b64, validate=True)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid templateImageBase64")

        arr = np.frombuffer(binary, dtype=np.uint8)
        decoded = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if decoded is None:
            raise HTTPException(status_code=400, detail="templateImageBase64 is not a supported image")
        template = cast(NDArray[np.uint8], decoded)

    if template is None and bool(req.templateFromLive):
        frame = svc.GetLatestCapture()
        if frame is None:
            raise HTTPException(status_code=404, detail="No captured frame available for templateFromLive. Start capture first.")
        template = _crop_frame_normalized(frame, req.roi)

    item = svc.AddConditionItemNewUuid(
        name=name,
        type=ConditionType[req.type.name],
        roi=ConditionRoi(
            xNormalized=float(req.roi.xNormalized),
            yNormalized=float(req.roi.yNormalized),
            widthNormalized=float(req.roi.widthNormalized),
            heightNormalized=float(req.roi.heightNormalized),
        ),
        templateImage=template,
    )

    _try_save_state(svc)
    return {"ok": True, "uuid": str(item.uuid)}


@app.post("/api/conditions/clear")
def ClearConditions():
    svc = _get_services()
    svc.ClearConditionItems()
    _try_save_state(svc)
    return {"ok": True}


@app.post("/api/conditions/remove_uuid")
def RemoveConditionByUuid(req: ConditionUuidRequest):
    svc = _get_services()
    try:
        svc.RemoveConditionItemByUuid(req.uuid)
    except KeyError:
        raise HTTPException(status_code=404, detail="Condition uuid not found")
    _try_save_state(svc)
    return {"ok": True}


@app.post("/api/conditions/move")
def MoveCondition(req: ConditionMoveRequest):
    svc = _get_services()
    try:
        svc.MoveConditionItemByUuid(req.uuid, str(req.direction))
        _try_save_state(svc)
        return {"ok": True}
    except KeyError:
        raise HTTPException(status_code=404, detail="Condition uuid not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/conditions/set_from_live")
def SetConditionFromLive(req: ConditionSetFromLiveRequest):
    svc = _get_services()
    from .services import ConditionItem, ConditionRoi, ConditionType

    item = svc.GetConditionItemByUuid(req.uuid)
    if item is None:
        raise HTTPException(status_code=404, detail="Condition uuid not found")

    frame = svc.GetLatestCapture()
    if frame is None:
        raise HTTPException(status_code=404, detail="No captured frame available. Start capture first.")

    roi = ConditionRoi(
        xNormalized=float(req.roi.xNormalized),
        yNormalized=float(req.roi.yNormalized),
        widthNormalized=float(req.roi.widthNormalized),
        heightNormalized=float(req.roi.heightNormalized),
    )

    # Name/type updates are optional.
    new_name = (req.name or "").strip()
    if not new_name:
        new_name = item.name

    new_type = item.type
    if req.type is not None:
        new_type = ConditionType[req.type.name]

    # Template update policy:
    # - If templateImageBase64 provided: use it.
    # - Else if templateFromLive: crop from latest frame.
    # - Else: keep existing.
    template: Optional[NDArray[np.uint8]] = cast(Optional[NDArray[np.uint8]], item.templateImage)
    raw_b64 = (req.templateImageBase64 or "").strip()
    if raw_b64:
        if "," in raw_b64:
            raw_b64 = raw_b64.split(",", 1)[1]
        try:
            binary = base64.b64decode(raw_b64, validate=True)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid templateImageBase64")

        arr = np.frombuffer(binary, dtype=np.uint8)
        decoded = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if decoded is None:
            raise HTTPException(status_code=400, detail="templateImageBase64 is not a supported image")
        template = cast(NDArray[np.uint8], decoded)
    elif bool(req.templateFromLive):
        template = _crop_frame_normalized(frame, req.roi)

    updated = ConditionItem(
        uuid=item.uuid,
        name=new_name,
        type=new_type,
        roi=roi,
        templateImage=template,
    )

    try:
        svc.SetConditionItemByUuid(req.uuid, updated)
    except KeyError:
        raise HTTPException(status_code=404, detail="Condition uuid not found")
    _try_save_state(svc)
    return {"ok": True}


@app.get("/api/conditions/status")
def GetConditionsStatus() -> Dict[str, Any]:
    """Return condition status keyed by uuid.

    Payload shape:
      {"order": [uuid...], "byUuid": {uuid: {uuid,index,name,type,templateThumbBase64,cropThumbBase64,last}}}
    """
    svc = _get_services()
    snapshots = svc.GetConditionStatusSnapshots()

    order: List[str] = []
    by_uuid: Dict[str, Any] = {}

    for idx, s in enumerate(snapshots):
        key = str(s.uuid)
        order.append(key)
        by_uuid[key] = {
            "uuid": key,
            "index": int(idx),
            "name": s.name,
            "type": s.type.name,
            "templateThumbBase64": s.templateThumbBase64,
            "cropThumbBase64": s.cropThumbBase64,
            "last": s.last,
        }

    return {"order": order, "byUuid": by_uuid}


@app.get("/api/conditions/stream")
async def ConditionsStream(request: Request):
    """Stream condition status updates over SSE as compact JSON payloads."""
    svc = _get_services()

    async def event_stream():
        yield "retry: 1000\n\n"

        last_seq = svc.GetConditionStatusSequence()
        last_keepalive = time.monotonic()

        while True:
            if await request.is_disconnected():
                break

            seq = svc.GetConditionStatusSequence()
            if seq != last_seq:
                last_seq = seq
                snapshots = svc.GetConditionStatusSnapshots()
                order: List[str] = []
                by_uuid: Dict[str, Any] = {}

                for idx, s in enumerate(snapshots):
                    key = str(s.uuid)
                    order.append(key)
                    by_uuid[key] = {
                        "uuid": key,
                        "index": int(idx),
                        "name": s.name,
                        "type": s.type.name,
                        "templateThumbBase64": s.templateThumbBase64,
                        "cropThumbBase64": s.cropThumbBase64,
                        "last": s.last,
                    }

                data = json.dumps({"order": order, "byUuid": by_uuid}, separators=(",", ":"))
                yield f"event: status\ndata: {data}\n\n"

            now = time.monotonic()
            if now - last_keepalive >= 10.0:
                yield ": keepalive\n\n"
                last_keepalive = now

            await asyncio.sleep(0.2)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/api/conditions/remove")
def RemoveCondition(name: str) -> Dict[str, Any]:
    svc = _get_services()
    removed = svc.RemoveConditionItemsByName(name)
    _try_save_state(svc)
    return {"ok": True, "removed": int(removed)}
