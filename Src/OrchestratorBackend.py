from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Optional, cast
from urllib.parse import urljoin
from uuid import UUID

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from Src.OrchestratorServices import OrchestratorServices


app = FastAPI()


def _resource_root() -> Path:
    """Return the runtime root directory.

    - In development: project root (the folder containing `Src/` and static folders).
    - In PyInstaller onefile: the extraction directory (`sys._MEIPASS`).
    """
    mei_root = getattr(sys, "_MEIPASS", None)
    if mei_root:
        return Path(mei_root)
    return Path(__file__).resolve().parents[1]


_public_dir = _resource_root() / "public_orchestrator"
app.mount("/static", StaticFiles(directory=str(_public_dir)), name="static")


def _state_root() -> Path:
    """Where to store orchestrator persistent state.

    - In dev: project root
    - In packaged exe: folder next to the executable
    """
    if bool(getattr(sys, "frozen", False)):
        try:
            return Path(sys.executable).resolve().parent
        except Exception:
            return Path.cwd()
    return Path(__file__).resolve().parents[1]


_STATE_PATH = _state_root() / "orchestrator_state.json"


def _try_load_state(svc: OrchestratorServices) -> None:
    try:
        svc.LoadState(_STATE_PATH)
    except FileNotFoundError:
        return
    except Exception as exc:
        print(f"[orchestrator_state] Load failed: {exc}")


def _try_save_state(svc: OrchestratorServices) -> None:
    try:
        svc.SaveState(_STATE_PATH)
    except Exception as exc:
        print(f"[orchestrator_state] Save failed: {exc}")


def _get_services() -> OrchestratorServices:
    svc = getattr(app.state, "services", None)
    if svc is not None:
        if not bool(getattr(app.state, "stateLoaded", False)):
            _try_load_state(svc)
            app.state.stateLoaded = True
        return svc

    # Fallback: create lazily.
    svc = OrchestratorServices()
    _try_load_state(svc)
    app.state.services = svc
    app.state.stateLoaded = True
    return svc


@app.get("/")
def GetOrchestratorUi() -> FileResponse:
    ui_path = _public_dir / "orchestrator.html"
    return FileResponse(str(ui_path), media_type="text/html")


def _require_cluster_base_url(svc: OrchestratorServices, clusterUuid: UUID) -> str:
    record = svc.GetCluster(clusterUuid)
    if record is None:
        raise HTTPException(status_code=404, detail="cluster not found")
    base = (record.baseUrl or "").strip()
    if not base:
        raise HTTPException(status_code=400, detail="cluster baseUrl is not set")
    if not (base.startswith("http://") or base.startswith("https://")):
        raise HTTPException(status_code=400, detail="cluster baseUrl must start with http:// or https://")
    if not base.endswith("/"):
        base = base + "/"
    return base


async def _proxy_json(method: str, baseUrl: str, path: str, body: Optional[Dict[str, Any]] = None) -> Any:
    url = urljoin(baseUrl, path.lstrip("/"))
    timeout = httpx.Timeout(connect=3.0, read=20.0, write=10.0, pool=3.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            res = await client.request(method.upper(), url, json=body)
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail=f"cluster request failed: {exc}")

    content_type = res.headers.get("content-type", "")
    if res.status_code >= 400:
        detail: str
        if "application/json" in content_type:
            try:
                payload_any: Any = res.json()
                if isinstance(payload_any, dict):
                    payload = cast(Dict[str, Any], payload_any)
                    if "detail" in payload:
                        detail = str(payload.get("detail") or "")
                    else:
                        detail = str(payload)
                else:
                    detail = str(payload_any)
            except Exception:
                detail = res.text
        else:
            detail = res.text
        raise HTTPException(status_code=502, detail=f"cluster error ({res.status_code}): {detail}")

    if "application/json" in content_type:
        try:
            return res.json()
        except Exception:
            return res.text
    return res.text


@app.get("/api/orchestrator/info")
def GetOrchestratorInfo() -> Dict[str, Any]:
    svc = _get_services()
    return {"orchestratorUuid": str(svc.GetOrchestratorUuid())}


class CommissionClusterRequest(BaseModel):
    clusterUuid: UUID
    label: str
    baseUrl: Optional[str] = None


class CommissionClusterFromUrlRequest(BaseModel):
    baseUrl: str
    label: Optional[str] = None


def _normalize_base_url(raw: str) -> str:
    s = str(raw or "").strip()
    if not s:
        raise ValueError("baseUrl is required")

    # Allow users to type just "IP:PORT" or "HOST:PORT".
    if not (s.startswith("http://") or s.startswith("https://")):
        s = "http://" + s

    # Normalize to no trailing slash for storage.
    return s.rstrip("/")


def _default_label_from_base_url(base_url: str) -> str:
    s = str(base_url or "").strip()
    if not s:
        return "Cluster"
    # For something like http://127.0.0.1:8000 -> 127.0.0.1:8000
    if s.startswith("http://"):
        s = s[len("http://"):]
    elif s.startswith("https://"):
        s = s[len("https://"):]
    return s.strip("/") or "Cluster"


class ClusterItemDto(BaseModel):
    uuid: str
    label: str
    baseUrl: Optional[str]
    commissionedAtUnix: float
    decommissionedAtUnix: Optional[float] = None


def _to_dto(r: Any) -> ClusterItemDto:
    return ClusterItemDto(
        uuid=str(r.uuid),
        label=str(r.label),
        baseUrl=(None if r.baseUrl is None else str(r.baseUrl)),
        commissionedAtUnix=float(r.commissionedAtUnix),
        decommissionedAtUnix=(None if r.decommissionedAtUnix is None else float(r.decommissionedAtUnix)),
    )


class UpdateClusterRequest(BaseModel):
    label: Optional[str] = None
    baseUrl: Optional[str] = None


@app.post("/api/orchestrator/clusters/commission")
def CommissionCluster(req: CommissionClusterRequest) -> Dict[str, Any]:
    svc = _get_services()
    try:
        record = svc.CommissionCluster(req.clusterUuid, req.label, req.baseUrl)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    _try_save_state(svc)
    return {"ok": True, "cluster": _to_dto(record).model_dump()}


@app.post("/api/orchestrator/clusters/commission_from_url")
async def CommissionClusterFromUrl(req: CommissionClusterFromUrlRequest) -> Dict[str, Any]:
    svc = _get_services()
    try:
        base_url = _normalize_base_url(req.baseUrl)
        label = str(req.label or "").strip() or _default_label_from_base_url(base_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Discover the cluster UUID by asking the cluster directly.
    base_for_proxy = base_url if base_url.endswith("/") else base_url + "/"
    info = await _proxy_json("GET", base_for_proxy, "/api/server/info")
    if not isinstance(info, dict) or "serverUuid" not in info:
        raise HTTPException(status_code=502, detail="cluster /api/server/info did not return serverUuid")

    try:
        cluster_uuid = UUID(str(info.get("serverUuid") or "").strip())
    except Exception:
        raise HTTPException(status_code=502, detail="cluster /api/server/info returned invalid serverUuid")

    try:
        record = svc.CommissionCluster(cluster_uuid, label, base_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    _try_save_state(svc)
    return {"ok": True, "cluster": _to_dto(record).model_dump(), "discovered": {"serverUuid": str(cluster_uuid)}}


@app.get("/api/orchestrator/clusters")
def ListClusters(includeDecommissioned: bool = False) -> Dict[str, Any]:
    svc = _get_services()
    clusters = svc.ListClusters(includeDecommissioned=bool(includeDecommissioned))
    return {"clusters": [_to_dto(c).model_dump() for c in clusters]}


@app.get("/api/orchestrator/clusters/{clusterUuid}")
def GetCluster(clusterUuid: UUID) -> Dict[str, Any]:
    svc = _get_services()
    record = svc.GetCluster(clusterUuid)
    if record is None:
        raise HTTPException(status_code=404, detail="cluster not found")
    return {"cluster": _to_dto(record).model_dump()}


@app.post("/api/orchestrator/clusters/{clusterUuid}/update")
def UpdateCluster(clusterUuid: UUID, req: UpdateClusterRequest) -> Dict[str, Any]:
    svc = _get_services()
    existing = svc.GetCluster(clusterUuid)
    if existing is None:
        raise HTTPException(status_code=404, detail="cluster not found")

    label: Optional[str] = None
    if req.label is not None:
        label = str(req.label or "").strip()
        if not label:
            raise HTTPException(status_code=400, detail="label is required")

    base_url: Optional[str] = None
    if req.baseUrl is not None:
        raw = str(req.baseUrl or "").strip()
        base_url = _normalize_base_url(raw) if raw else None

    try:
        record = svc.UpdateCluster(clusterUuid, label=label, baseUrl=base_url)
    except KeyError:
        raise HTTPException(status_code=404, detail="cluster not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    _try_save_state(svc)
    return {"ok": True, "cluster": _to_dto(record).model_dump()}


@app.post("/api/orchestrator/clusters/{clusterUuid}/decommission")
def DecommissionCluster(clusterUuid: UUID) -> Dict[str, Any]:
    svc = _get_services()
    try:
        record = svc.DecommissionCluster(clusterUuid)
    except KeyError:
        raise HTTPException(status_code=404, detail="cluster not found")

    _try_save_state(svc)
    return {"ok": True, "cluster": _to_dto(record).model_dump()}


@app.post("/api/orchestrator/clusters/{clusterUuid}/remove")
def RemoveCluster(clusterUuid: UUID) -> Dict[str, Any]:
    svc = _get_services()
    try:
        svc.RemoveCluster(clusterUuid)
    except KeyError:
        raise HTTPException(status_code=404, detail="cluster not found")

    _try_save_state(svc)
    return {"ok": True}


class OrchestratorImportRequest(BaseModel):
    state: Dict[str, Any]


@app.get("/api/orchestrator/state/export")
def ExportOrchestratorState() -> Dict[str, Any]:
    svc = _get_services()
    return svc.ExportStateDict()


@app.post("/api/orchestrator/state/import")
def ImportOrchestratorState(req: OrchestratorImportRequest) -> Dict[str, Any]:
    svc = _get_services()
    try:
        svc.ImportStateDict(dict(req.state))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Import failed: {exc}")

    _try_save_state(svc)
    return {"ok": True}


@app.post("/api/orchestrator/state/reload")
def ReloadOrchestratorState() -> Dict[str, Any]:
    svc = _get_services()
    try:
        svc.LoadState(_STATE_PATH)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="orchestrator_state.json not found")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Reload failed: {exc}")

    try:
        app.state.stateLoaded = True
    except Exception:
        pass

    return {"ok": True, "orchestratorUuid": str(svc.GetOrchestratorUuid())}


# -----------------------------------------------------------------------------
# Cluster management proxies (Actions / Conditions / Triggers)
# -----------------------------------------------------------------------------


@app.get("/api/orchestrator/clusters/{clusterUuid}/server/info")
async def ProxyServerInfo(clusterUuid: UUID) -> Any:
    svc = _get_services()
    base = _require_cluster_base_url(svc, clusterUuid)
    return await _proxy_json("GET", base, "/api/server/info")


@app.get("/api/orchestrator/clusters/{clusterUuid}/actions")
async def ProxyActionsList(clusterUuid: UUID) -> Any:
    svc = _get_services()
    base = _require_cluster_base_url(svc, clusterUuid)
    return await _proxy_json("GET", base, "/api/actions")


class ProxyBodyRequest(BaseModel):
    body: Dict[str, Any]


@app.get("/api/orchestrator/clusters/{clusterUuid}/app/defaults")
async def ProxyAppDefaults(clusterUuid: UUID) -> Any:
    svc = _get_services()
    base = _require_cluster_base_url(svc, clusterUuid)
    return await _proxy_json("GET", base, "/api/app/defaults")


@app.post("/api/orchestrator/clusters/{clusterUuid}/app/launch")
async def ProxyAppLaunch(clusterUuid: UUID, req: ProxyBodyRequest) -> Any:
    svc = _get_services()
    base = _require_cluster_base_url(svc, clusterUuid)
    return await _proxy_json("POST", base, "/api/app/launch", body=dict(req.body))


@app.post("/api/orchestrator/clusters/{clusterUuid}/app/attach")
async def ProxyAppAttach(clusterUuid: UUID, req: ProxyBodyRequest) -> Any:
    svc = _get_services()
    base = _require_cluster_base_url(svc, clusterUuid)
    return await _proxy_json("POST", base, "/api/app/attach", body=dict(req.body))


@app.post("/api/orchestrator/clusters/{clusterUuid}/app/close")
async def ProxyAppClose(clusterUuid: UUID) -> Any:
    svc = _get_services()
    base = _require_cluster_base_url(svc, clusterUuid)
    return await _proxy_json("POST", base, "/api/app/close")


@app.post("/api/orchestrator/clusters/{clusterUuid}/capture/start")
async def ProxyCaptureStart(clusterUuid: UUID, req: ProxyBodyRequest) -> Any:
    svc = _get_services()
    base = _require_cluster_base_url(svc, clusterUuid)
    return await _proxy_json("POST", base, "/api/capture/start", body=dict(req.body))


@app.post("/api/orchestrator/clusters/{clusterUuid}/capture/stop")
async def ProxyCaptureStop(clusterUuid: UUID) -> Any:
    svc = _get_services()
    base = _require_cluster_base_url(svc, clusterUuid)
    return await _proxy_json("POST", base, "/api/capture/stop")


@app.post("/api/orchestrator/clusters/{clusterUuid}/actions/upsert")
async def ProxyActionsUpsert(clusterUuid: UUID, req: ProxyBodyRequest) -> Any:
    svc = _get_services()
    base = _require_cluster_base_url(svc, clusterUuid)
    return await _proxy_json("POST", base, "/api/actions/upsert", body=dict(req.body))


@app.post("/api/orchestrator/clusters/{clusterUuid}/actions/remove_uuid")
async def ProxyActionsRemove(clusterUuid: UUID, req: ProxyBodyRequest) -> Any:
    svc = _get_services()
    base = _require_cluster_base_url(svc, clusterUuid)
    return await _proxy_json("POST", base, "/api/actions/remove_uuid", body=dict(req.body))


@app.post("/api/orchestrator/clusters/{clusterUuid}/actions/run")
async def ProxyActionsRun(clusterUuid: UUID, req: ProxyBodyRequest) -> Any:
    svc = _get_services()
    base = _require_cluster_base_url(svc, clusterUuid)
    return await _proxy_json("POST", base, "/api/actions/run", body=dict(req.body))


@app.get("/api/orchestrator/clusters/{clusterUuid}/conditions")
async def ProxyConditionsList(clusterUuid: UUID) -> Any:
    svc = _get_services()
    base = _require_cluster_base_url(svc, clusterUuid)
    return await _proxy_json("GET", base, "/api/conditions")


@app.get("/api/orchestrator/clusters/{clusterUuid}/conditions/status")
async def ProxyConditionsStatus(clusterUuid: UUID) -> Any:
    svc = _get_services()
    base = _require_cluster_base_url(svc, clusterUuid)
    return await _proxy_json("GET", base, "/api/conditions/status")


@app.post("/api/orchestrator/clusters/{clusterUuid}/conditions")
async def ProxyConditionsCreate(clusterUuid: UUID, req: ProxyBodyRequest) -> Any:
    svc = _get_services()
    base = _require_cluster_base_url(svc, clusterUuid)
    return await _proxy_json("POST", base, "/api/conditions", body=dict(req.body))


@app.post("/api/orchestrator/clusters/{clusterUuid}/conditions/set_from_live")
async def ProxyConditionsSetFromLive(clusterUuid: UUID, req: ProxyBodyRequest) -> Any:
    svc = _get_services()
    base = _require_cluster_base_url(svc, clusterUuid)
    return await _proxy_json("POST", base, "/api/conditions/set_from_live", body=dict(req.body))


@app.post("/api/orchestrator/clusters/{clusterUuid}/conditions/move")
async def ProxyConditionsMove(clusterUuid: UUID, req: ProxyBodyRequest) -> Any:
    svc = _get_services()
    base = _require_cluster_base_url(svc, clusterUuid)
    return await _proxy_json("POST", base, "/api/conditions/move", body=dict(req.body))


@app.post("/api/orchestrator/clusters/{clusterUuid}/conditions/remove_uuid")
async def ProxyConditionsRemove(clusterUuid: UUID, req: ProxyBodyRequest) -> Any:
    svc = _get_services()
    base = _require_cluster_base_url(svc, clusterUuid)
    return await _proxy_json("POST", base, "/api/conditions/remove_uuid", body=dict(req.body))


@app.get("/api/orchestrator/clusters/{clusterUuid}/triggers")
async def ProxyTriggersList(clusterUuid: UUID) -> Any:
    svc = _get_services()
    base = _require_cluster_base_url(svc, clusterUuid)
    return await _proxy_json("GET", base, "/api/triggers")


@app.get("/api/orchestrator/clusters/{clusterUuid}/triggers/status")
async def ProxyTriggersStatus(clusterUuid: UUID) -> Any:
    svc = _get_services()
    base = _require_cluster_base_url(svc, clusterUuid)
    return await _proxy_json("GET", base, "/api/triggers/status")


@app.post("/api/orchestrator/clusters/{clusterUuid}/triggers/upsert")
async def ProxyTriggersUpsert(clusterUuid: UUID, req: ProxyBodyRequest) -> Any:
    svc = _get_services()
    base = _require_cluster_base_url(svc, clusterUuid)
    return await _proxy_json("POST", base, "/api/triggers/upsert", body=dict(req.body))


@app.post("/api/orchestrator/clusters/{clusterUuid}/triggers/remove_uuid")
async def ProxyTriggersRemove(clusterUuid: UUID, req: ProxyBodyRequest) -> Any:
    svc = _get_services()
    base = _require_cluster_base_url(svc, clusterUuid)
    return await _proxy_json("POST", base, "/api/triggers/remove_uuid", body=dict(req.body))


@app.post("/api/orchestrator/clusters/{clusterUuid}/triggers/set_enabled")
async def ProxyTriggersSetEnabled(clusterUuid: UUID, req: ProxyBodyRequest) -> Any:
    svc = _get_services()
    base = _require_cluster_base_url(svc, clusterUuid)
    return await _proxy_json("POST", base, "/api/triggers/set_enabled", body=dict(req.body))
