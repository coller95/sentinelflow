from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os

from Src.Services import Services

app = FastAPI()
services = Services()

_public_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "public")
app.mount("/static", StaticFiles(directory=_public_dir), name="static")


def _get_services() -> Services:
    # Prefer an instance wired by the entrypoint (Main.py), but fall back
    # to the module-level instance for backwards compatibility.
    return getattr(app.state, "services", services)


class LaunchRequest(BaseModel):
    app_path: str


class AttachRequest(BaseModel):
    window_title: str


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
