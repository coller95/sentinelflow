from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.responses import Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import sys
import time
from pathlib import Path
from enum import Enum
import base64
import json

import cv2
import numpy as np

from typing import List, Optional

from Src.ControllerServices import ControllerServices

app = FastAPI()
services: Optional[ControllerServices] = None

def _resource_root() -> Path:
    """Return the runtime root directory.

    - In development: project root (the folder containing `Src/` and `public/`).
    - In PyInstaller onefile: the extraction directory (`sys._MEIPASS`).
    """
    mei_root = getattr(sys, "_MEIPASS", None)
    if mei_root:
        return Path(mei_root)
    return Path(__file__).resolve().parents[1]


_public_dir = _resource_root() / "public"
app.mount("/static", StaticFiles(directory=str(_public_dir)), name="static")


def _get_services() -> ControllerServices:
    # Prefer an instance wired by the entrypoint (Main.py), but fall back
    # to the module-level instance for backwards compatibility.
    svc = getattr(app.state, "services", None)
    if svc is not None:
        return svc

    global services
    if services is None:
        services = ControllerServices()
    return services


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


class CaptureStartRequest(BaseModel):
    intervalSeconds: float = 1.0


class ClickRequest(BaseModel):
    x: float
    y: float


class KeyRequest(BaseModel):
    keyName: str


class ConditionTypeDto(str, Enum):
    ImageMatchRoi = "ImageMatchRoi"
    ProgressBar = "ProgressBar"


class ConditionRoiDto(BaseModel):
    xNormalized: float
    yNormalized: float
    widthNormalized: float
    heightNormalized: float


class ConditionItemDto(BaseModel):
    name: str
    type: ConditionTypeDto
    roi: ConditionRoiDto


class ConditionStatusDto(BaseModel):
    index: int
    name: str
    type: ConditionTypeDto
    templateThumbBase64: Optional[str] = None
    cropThumbBase64: Optional[str] = None
    last: Optional[float] = None


class ConditionIndexRequest(BaseModel):
    index: int


class ConditionMoveRequest(BaseModel):
    index: int
    direction: str  # 'up' | 'down'


class ConditionSetFromLiveRequest(BaseModel):
    index: int
    roi: ConditionRoiDto
    setTemplate: bool = True


class ConditionUpsertRequest(BaseModel):
    name: str
    type: ConditionTypeDto
    roi: ConditionRoiDto
    templateImageBase64: Optional[str] = None
    templateFromLive: bool = False


def _crop_frame_normalized(frame: np.ndarray, roi: ConditionRoiDto) -> np.ndarray:
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


def _encode_thumb_b64(img: np.ndarray, max_size: int = 64) -> str:
    h, w = img.shape[:2]
    if h <= 0 or w <= 0:
        return ""
    scale = float(max_size) / float(max(h, w))
    if scale < 1.0:
        new_w = max(1, int(round(w * scale)))
        new_h = max(1, int(round(h * scale)))
        img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
    ok, encoded = cv2.imencode(".jpg", img)
    if not ok:
        return ""
    return base64.b64encode(encoded.tobytes()).decode("ascii")


# Serve the HTML file from the public directory
@app.get("/", response_class=FileResponse)
def ServeIndex():
    index_path = _public_dir / "index.html"
    return FileResponse(str(index_path), media_type="text/html")


@app.post("/api/app/launch")
def LaunchApp(req: LaunchRequest):
    svc = _get_services()
    svc.LaunchApp(req.app_path, left=req.left, top=req.top, width=req.width, height=req.height)
    return {"ok": True}


@app.post("/api/app/attach")
def AttachApp(req: AttachRequest):
    svc = _get_services()
    svc.AttachApp(req.window_title, left=req.left, top=req.top, width=req.width, height=req.height)
    return {"ok": True}


@app.post("/api/app/close")
def CloseApp():
    svc = _get_services()
    svc.CloseApp()
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
def CaptureEvents():
    svc = _get_services()

    def event_stream():
        # Send an initial retry hint to the browser.
        yield "retry: 1000\n\n"

        last_seq = svc.GetCaptureSequence()
        last_keepalive = time.monotonic()

        while True:
            seq = svc.GetCaptureSequence()
            if seq != last_seq and seq > 0:
                last_seq = seq
                yield f"event: frame\ndata: {seq}\n\n"

            now = time.monotonic()
            if now - last_keepalive >= 10.0:
                # Comment line as keepalive.
                yield ": keepalive\n\n"
                last_keepalive = now

            time.sleep(0.2)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/api/capture/stream")
def CaptureStream(fmt: str = "jpg", quality: int = 70):
    """Stream captured frames over SSE as base64-encoded image payloads.

    This avoids a second HTTP request per frame (no /api/capture/latest polling).
    """
    svc = _get_services()

    normalized = (fmt or "jpg").lower().strip(".")
    if normalized not in ("jpg", "jpeg"):
        raise HTTPException(status_code=400, detail="fmt must be 'jpg'")

    q = int(quality)
    q = max(10, min(95, q))

    def event_stream():
        yield "retry: 1000\n\n"

        last_seq = svc.GetCaptureSequence()
        last_keepalive = time.monotonic()

        while True:
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

            time.sleep(0.2)

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


@app.get("/api/conditions")
def GetConditions() -> List[ConditionItemDto]:
    svc = _get_services()
    items = []
    for item in svc.GetConditionItems():
        items.append(
            ConditionItemDto(
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
def AddCondition(req: ConditionUpsertRequest):
    svc = _get_services()

    name = (req.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name cannot be empty")

    if req.roi.widthNormalized <= 0 or req.roi.heightNormalized <= 0:
        raise HTTPException(status_code=400, detail="roi width/height must be > 0")

    from Src.ControllerServices import ConditionItem, ConditionRoi, ConditionType

    template = None
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
        template = decoded

    if template is None and bool(req.templateFromLive):
        frame = svc.GetLatestCapture()
        if frame is None:
            raise HTTPException(status_code=404, detail="No captured frame available for templateFromLive. Start capture first.")
        template = _crop_frame_normalized(frame, req.roi)

    item = ConditionItem(
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

    svc.AddConditionItem(item)
    return {"ok": True}


@app.post("/api/conditions/clear")
def ClearConditions():
    svc = _get_services()
    svc.ClearConditionItems()
    return {"ok": True}


@app.post("/api/conditions/remove_index")
def RemoveConditionByIndex(req: ConditionIndexRequest):
    svc = _get_services()
    try:
        svc.RemoveConditionItemByIndex(int(req.index))
    except IndexError:
        raise HTTPException(status_code=404, detail="Condition index out of range")
    return {"ok": True}


@app.post("/api/conditions/move")
def MoveCondition(req: ConditionMoveRequest):
    svc = _get_services()
    try:
        new_index = svc.MoveConditionItem(int(req.index), str(req.direction))
    except IndexError:
        raise HTTPException(status_code=404, detail="Condition index out of range")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True, "index": int(new_index)}


@app.post("/api/conditions/set_from_live")
def SetConditionFromLive(req: ConditionSetFromLiveRequest):
    svc = _get_services()
    from Src.ControllerServices import ConditionItem, ConditionRoi, ConditionType

    item = svc.GetConditionItem(int(req.index))
    if item is None:
        raise HTTPException(status_code=404, detail="Condition index out of range")

    frame = svc.GetLatestCapture()
    if frame is None:
        raise HTTPException(status_code=404, detail="No captured frame available. Start capture first.")

    roi = ConditionRoi(
        xNormalized=float(req.roi.xNormalized),
        yNormalized=float(req.roi.yNormalized),
        widthNormalized=float(req.roi.widthNormalized),
        heightNormalized=float(req.roi.heightNormalized),
    )

    template = item.templateImage
    if bool(req.setTemplate):
        template = _crop_frame_normalized(frame, req.roi)

    updated = ConditionItem(
        name=item.name,
        type=ConditionType[item.type.name],
        roi=roi,
        templateImage=template,
    )
    svc.SetConditionItem(int(req.index), updated)
    return {"ok": True}


@app.get("/api/conditions/status")
def GetConditionsStatus() -> List[ConditionStatusDto]:
    svc = _get_services()
    snapshots = svc.GetConditionStatusSnapshots()
    out: List[ConditionStatusDto] = []
    for s in snapshots:
        out.append(
            ConditionStatusDto(
                index=int(s.index),
                name=s.name,
                type=ConditionTypeDto[s.type.name],
                templateThumbBase64=s.templateThumbBase64,
                cropThumbBase64=s.cropThumbBase64,
                last=s.last,
            )
        )
    return out


@app.get("/api/conditions/stream")
def ConditionsStream():
    """Stream condition status updates over SSE as compact JSON payloads."""
    svc = _get_services()

    def event_stream():
        yield "retry: 1000\n\n"

        last_seq = svc.GetConditionStatusSequence()
        last_keepalive = time.monotonic()

        while True:
            seq = svc.GetConditionStatusSequence()
            if seq != last_seq:
                last_seq = seq
                snapshots = svc.GetConditionStatusSnapshots()
                payload = []
                for s in snapshots:
                    payload.append(
                        {
                            "index": int(s.index),
                            "name": s.name,
                            "type": s.type.name,
                            "templateThumbBase64": s.templateThumbBase64,
                            "cropThumbBase64": s.cropThumbBase64,
                            "last": s.last,
                        }
                    )
                data = json.dumps(payload, separators=(",", ":"))
                yield f"event: status\ndata: {data}\n\n"

            now = time.monotonic()
            if now - last_keepalive >= 10.0:
                yield ": keepalive\n\n"
                last_keepalive = now

            time.sleep(0.2)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/api/conditions/remove")
def RemoveCondition(name: str):
    svc = _get_services()
    removed = svc.RemoveConditionItemsByName(name)
    return {"ok": True, "removed": int(removed)}
