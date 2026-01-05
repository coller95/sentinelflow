from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.responses import Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import sys
import time
from pathlib import Path

import cv2

from typing import Optional

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
