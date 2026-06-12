"""HTTP client for the sentinelflow cluster node API."""

import numpy as np
import cv2
import requests
from requests import Session


class NodeError(Exception):
    """Raised when the node API returns an error or unexpected response."""


class NoFrameYet(NodeError):
    """Raised by capture_latest when the server returns 404 (no frame captured yet)."""


class NodeClient:
    """Thin wrapper around the sentinelflow node HTTP API.

    All methods raise NodeError on connection error, non-2xx status, or
    bad/missing payload.  None is never returned silently.
    """

    def __init__(self, base_url: str, timeout_s: float = 5.0) -> None:
        """Create a client pointing at *base_url* (no trailing slash)."""
        self._base = base_url.rstrip("/")
        self._timeout = timeout_s
        self._session: Session = requests.Session()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get(self, path: str, **kwargs) -> requests.Response:
        try:
            r = self._session.get(
                f"{self._base}{path}", timeout=self._timeout, **kwargs
            )
        except requests.RequestException as exc:
            raise NodeError(f"GET {path} connection error: {exc}") from exc
        if not r.ok:
            raise NodeError(f"GET {path} -> HTTP {r.status_code}: {r.text[:200]}")
        return r

    def _post(self, path: str, payload: dict) -> requests.Response:
        try:
            r = self._session.post(
                f"{self._base}{path}",
                json=payload,
                timeout=self._timeout,
            )
        except requests.RequestException as exc:
            raise NodeError(f"POST {path} connection error: {exc}") from exc
        if not r.ok:
            raise NodeError(f"POST {path} -> HTTP {r.status_code}: {r.text[:200]}")
        return r

    # ------------------------------------------------------------------
    # API methods
    # ------------------------------------------------------------------

    def server_info(self) -> dict:
        """GET /api/server/info — returns server metadata dict."""
        r = self._get("/api/server/info")
        try:
            return r.json()
        except ValueError as exc:
            raise NodeError(f"server_info: invalid JSON: {exc}") from exc

    def app_status(self) -> dict:
        """GET /api/app/status — returns attachment/process status dict."""
        r = self._get("/api/app/status")
        try:
            return r.json()
        except ValueError as exc:
            raise NodeError(f"app_status: invalid JSON: {exc}") from exc

    def capture_start(self, interval_s: float = 0.5) -> None:
        """POST /api/capture/start — begin periodic screen capture."""
        self._post("/api/capture/start", {"intervalSeconds": interval_s})

    def capture_latest(self) -> np.ndarray:
        """GET /api/capture/latest?fmt=png — return latest frame as BGR ndarray.

        Raises NoFrameYet if the server returns 404 (no frame captured yet).
        """
        try:
            r = self._session.get(
                f"{self._base}/api/capture/latest",
                params={"fmt": "png"},
                timeout=self._timeout,
            )
        except requests.RequestException as exc:
            raise NodeError(f"capture_latest connection error: {exc}") from exc
        if r.status_code == 404:
            raise NoFrameYet("no frame yet")
        if not r.ok:
            raise NodeError(
                f"capture_latest -> HTTP {r.status_code}: {r.text[:200]}"
            )
        arr = np.frombuffer(r.content, np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is None:
            raise NodeError("capture_latest: imdecode returned None (corrupt image?)")
        return frame

    def click(self, x: float, y: float) -> None:
        """POST /api/control/click — click at normalized (x, y) in [0..1]."""
        self._post("/api/control/click", {"x": x, "y": y})

    def key(self, key_name: str) -> None:
        """POST /api/control/key — send a key by name."""
        self._post("/api/control/key", {"keyName": key_name})
