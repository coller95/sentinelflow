from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.responses import Response
from pydantic import BaseModel
import os

import cv2

from typing import Optional

from Src.Services import Services

app = FastAPI()
services: Optional[Services] = None

_public_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "public")
app.mount("/static", StaticFiles(directory=_public_dir), name="static")


def _get_services() -> Services:
    # Prefer an instance wired by the entrypoint (Main.py), but fall back
    # to the module-level instance for backwards compatibility.
    svc = getattr(app.state, "services", None)
    if svc is not None:
        return svc

    global services
    if services is None:
        services = Services()
    return services


class LaunchRequest(BaseModel):
    app_path: str


class AttachRequest(BaseModel):
    window_title: str


class CaptureStartRequest(BaseModel):
    intervalSeconds: float = 1.0


# Serve the HTML file from the public directory
@app.get("/", response_class=FileResponse)
def ServeIndex():
    indexPath = os.path.join(os.path.dirname(os.path.dirname(__file__)), "public", "index.html")
    return FileResponse(indexPath, media_type="text/html")


@app.post("/api/app/launch")
def LaunchApp(req: LaunchRequest):
    svc = _get_services()
    svc.LaunchApp(req.app_path)
    return {"ok": True}


@app.post("/api/app/attach")
def AttachApp(req: AttachRequest):
    svc = _get_services()
    svc.AttachApp(req.window_title)
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
