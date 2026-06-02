from __future__ import annotations

import base64
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

import cv2
import numpy as np


def resource_root() -> Path:
    """Return the runtime root directory.

    - In development: project root (the folder containing `Src/` and `web/`).
    - In PyInstaller onefile: the extraction directory (`sys._MEIPASS`).
    """
    mei_root = getattr(sys, "_MEIPASS", None)
    if mei_root:
        return Path(mei_root)
    # Orchestrator is in Src/orchestrator/utils.py -> parents[2] is project root
    return Path(__file__).resolve().parents[2]


def state_root() -> Path:
    """Where to store orchestrator persistent state.

    - In dev: project root
    - In packaged exe: folder next to the executable
    """
    if bool(getattr(sys, "frozen", False)):
        try:
            return Path(sys.executable).resolve().parent
        except Exception:
            return Path.cwd()
    # Orchestrator is in Src/orchestrator/utils.py -> parents[2] is project root
    return Path(__file__).resolve().parents[2]


def normalize_base_url(raw: str) -> str:
    s = str(raw or "").strip()
    if not s:
        raise ValueError("baseUrl is required")

    # Allow users to type just "IP:PORT" or "HOST:PORT".
    if not (s.startswith("http://") or s.startswith("https://")):
        s = "http://" + s

    # Normalize to no trailing slash for storage.
    return s.rstrip("/")


def default_label_from_base_url(base_url: str) -> str:
    s = str(base_url or "").strip()
    if not s:
        return "Cluster"
    # For something like http://127.0.0.1:8000 -> 127.0.0.1:8000
    if s.startswith("http://"):
        s = s[len("http://"):]
    elif s.startswith("https://"):
        s = s[len("https://"):]
    return s.strip("/") or "Cluster"


def find_item_index(items: List[Dict[str, Any]], uuid_str: str) -> int:
    for i, item in enumerate(items):
        if str(item.get("uuid", "")).strip() == uuid_str:
            return i
    return -1


def decode_image_b64(b64: Optional[str]) -> Optional[np.ndarray]:
    raw = (b64 or "").strip()
    if not raw:
        return None
    if "," in raw:
        raw = raw.split(",", 1)[1]
    try:
        binary = base64.b64decode(raw, validate=True)
    except Exception:
        return None
    arr = np.frombuffer(binary, dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def encode_jpeg_b64(img: Optional[np.ndarray], quality: Optional[int] = None) -> Optional[str]:
    if img is None or getattr(img, "size", 0) == 0:
        return None
    
    params = []
    if quality is not None:
        params = [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)]
        
    ok, encoded = cv2.imencode(".jpg", img, params)
    if not ok:
        return None
    return base64.b64encode(encoded.tobytes()).decode("ascii")


def encode_png_b64(img: Optional[np.ndarray]) -> Optional[str]:
    if img is None or getattr(img, "size", 0) == 0:
        return None
    ok, encoded = cv2.imencode(".png", img)
    if not ok:
        return None
    return base64.b64encode(encoded.tobytes()).decode("ascii")


def crop_frame_normalized(frame: Optional[np.ndarray], roi: Dict[str, Any]) -> Optional[np.ndarray]:
    if frame is None or getattr(frame, "size", 0) == 0:
        return None
    h, w = frame.shape[:2]
    if w <= 0 or h <= 0:
        return None

    x = float(max(0.0, min(1.0, roi.get("xNormalized", 0.0) or 0.0)))
    y = float(max(0.0, min(1.0, roi.get("yNormalized", 0.0) or 0.0)))
    rw = float(max(0.0, min(1.0, roi.get("widthNormalized", 0.0) or 0.0)))
    rh = float(max(0.0, min(1.0, roi.get("heightNormalized", 0.0) or 0.0)))

    px = int(x * w)
    py = int(y * h)
    pw = int(rw * w)
    ph = int(rh * h)

    px = max(0, min(px, w - 1))
    py = max(0, min(py, h - 1))
    pw = max(1, min(pw, w - px))
    ph = max(1, min(ph, h - py))
    return frame[py:py + ph, px:px + pw].copy()
