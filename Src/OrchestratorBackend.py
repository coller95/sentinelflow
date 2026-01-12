from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, cast
from urllib.parse import urljoin
from uuid import UUID

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel

from Src.OrchestratorServices import OrchestratorServices


app = FastAPI()


# -----------------------------------------------------------------------------
# Runtime paths + persistence
# -----------------------------------------------------------------------------

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


# -----------------------------------------------------------------------------
# UI
# -----------------------------------------------------------------------------

@app.get("/")
def GetOrchestratorUi() -> FileResponse:
    ui_path = _public_dir / "orchestrator.html"
    return FileResponse(str(ui_path), media_type="text/html")


# -----------------------------------------------------------------------------
# Cluster proxy helpers
# -----------------------------------------------------------------------------

def _require_cluster_base_url(svc: OrchestratorServices, clusterUuid: UUID) -> str:
    record = svc.GetCluster(clusterUuid)
    if record is None:
        raise HTTPException(status_code=404, detail="cluster not found")

    dupes = svc.FindClustersByServerUuid(record.serverUuid, includeDecommissioned=False)
    if len(dupes) > 1:
        base_urls = [str(c.baseUrl or "") for c in dupes if c.baseUrl]
        suffix = f" ({', '.join(base_urls)})" if base_urls else ""
        raise HTTPException(
            status_code=409,
            detail=f"duplicate serverUuid detected; resolve duplicates before proxying{suffix}",
        )

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


async def _proxy_bytes(method: str, baseUrl: str, path: str) -> Response:
    url = urljoin(baseUrl, path.lstrip("/"))
    timeout = httpx.Timeout(connect=3.0, read=20.0, write=10.0, pool=3.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            res = await client.request(method.upper(), url)
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail=f"cluster request failed: {exc}")

    if res.status_code >= 400:
        content_type = res.headers.get("content-type", "")
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

    media = res.headers.get("content-type", "application/octet-stream")
    return Response(content=res.content, media_type=media, headers={"Cache-Control": "no-store"})


async def _proxy_sse(baseUrl: str, path: str) -> StreamingResponse:
    url = urljoin(baseUrl, path.lstrip("/"))
    timeout = httpx.Timeout(connect=3.0, read=None, write=10.0, pool=3.0)

    async def event_stream():
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                async with client.stream("GET", url) as res:
                    if res.status_code >= 400:
                        raw = await res.aread()
                        detail = raw.decode("utf-8", errors="replace")
                        raise HTTPException(status_code=502, detail=f"cluster error ({res.status_code}): {detail}")
                    async for chunk in res.aiter_bytes():
                        if chunk:
                            yield chunk
            except httpx.RequestError as exc:
                raise HTTPException(status_code=502, detail=f"cluster request failed: {exc}")

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store"},
    )


# -----------------------------------------------------------------------------
# Orchestrator info
# -----------------------------------------------------------------------------

@app.get("/api/orchestrator/info")
def GetOrchestratorInfo() -> Dict[str, Any]:
    svc = _get_services()
    return {"orchestratorUuid": str(svc.GetOrchestratorUuid())}


# -----------------------------------------------------------------------------
# Cluster management models
# -----------------------------------------------------------------------------

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
    serverUuid: str
    label: str
    baseUrl: Optional[str]
    commissionedAtUnix: float
    decommissionedAtUnix: Optional[float] = None
    duplicateCount: int = 0
    isDuplicate: bool = False


def _to_dto(r: Any, duplicateCount: int = 0) -> ClusterItemDto:
    return ClusterItemDto(
        uuid=str(r.uuid),
        serverUuid=str(r.serverUuid),
        label=str(r.label),
        baseUrl=(None if r.baseUrl is None else str(r.baseUrl)),
        commissionedAtUnix=float(r.commissionedAtUnix),
        decommissionedAtUnix=(None if r.decommissionedAtUnix is None else float(r.decommissionedAtUnix)),
        duplicateCount=int(duplicateCount),
        isDuplicate=int(duplicateCount) > 1,
    )


def _duplicate_server_uuid_counts(clusters: list[Any]) -> Dict[UUID, int]:
    counts: Dict[UUID, int] = {}
    for c in clusters:
        if c is None:
            continue
        if getattr(c, "decommissionedAtUnix", None) is not None:
            continue
        su = getattr(c, "serverUuid", None)
        if su is None:
            continue
        counts[su] = counts.get(su, 0) + 1
    return counts


class UpdateClusterRequest(BaseModel):
    label: Optional[str] = None
    baseUrl: Optional[str] = None


# -----------------------------------------------------------------------------
# Cluster management routes
# -----------------------------------------------------------------------------

@app.post("/api/orchestrator/clusters/commission")
def CommissionCluster(req: CommissionClusterRequest) -> Dict[str, Any]:
    svc = _get_services()
    try:
        record = svc.CommissionCluster(req.clusterUuid, req.label, req.baseUrl)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    dup_counts = _duplicate_server_uuid_counts(svc.ListClusters(includeDecommissioned=True))
    _try_save_state(svc)
    return {"ok": True, "cluster": _to_dto(record, dup_counts.get(record.serverUuid, 0)).model_dump()}


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
        server_uuid = UUID(str(info.get("serverUuid") or "").strip())
    except Exception:
        raise HTTPException(status_code=502, detail="cluster /api/server/info returned invalid serverUuid")

    try:
        record = svc.CommissionCluster(server_uuid, label, base_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    dup_counts = _duplicate_server_uuid_counts(svc.ListClusters(includeDecommissioned=True))
    _try_save_state(svc)
    return {
        "ok": True,
        "cluster": _to_dto(record, dup_counts.get(record.serverUuid, 0)).model_dump(),
        "discovered": {"serverUuid": str(server_uuid)},
    }


@app.get("/api/orchestrator/clusters")
def ListClusters(includeDecommissioned: bool = False) -> Dict[str, Any]:
    svc = _get_services()
    clusters = svc.ListClusters(includeDecommissioned=bool(includeDecommissioned))
    dup_counts = _duplicate_server_uuid_counts(clusters)
    return {"clusters": [_to_dto(c, dup_counts.get(c.serverUuid, 0)).model_dump() for c in clusters]}


@app.get("/api/orchestrator/clusters/{clusterUuid}")
def GetCluster(clusterUuid: UUID) -> Dict[str, Any]:
    svc = _get_services()
    record = svc.GetCluster(clusterUuid)
    if record is None:
        raise HTTPException(status_code=404, detail="cluster not found")
    dup_counts = _duplicate_server_uuid_counts(svc.ListClusters(includeDecommissioned=True))
    return {"cluster": _to_dto(record, dup_counts.get(record.serverUuid, 0)).model_dump()}


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

    dup_counts = _duplicate_server_uuid_counts(svc.ListClusters(includeDecommissioned=True))
    _try_save_state(svc)
    return {"ok": True, "cluster": _to_dto(record, dup_counts.get(record.serverUuid, 0)).model_dump()}


@app.post("/api/orchestrator/clusters/{clusterUuid}/decommission")
def DecommissionCluster(clusterUuid: UUID) -> Dict[str, Any]:
    svc = _get_services()
    try:
        record = svc.DecommissionCluster(clusterUuid)
    except KeyError:
        raise HTTPException(status_code=404, detail="cluster not found")

    dup_counts = _duplicate_server_uuid_counts(svc.ListClusters(includeDecommissioned=True))
    _try_save_state(svc)
    return {"ok": True, "cluster": _to_dto(record, dup_counts.get(record.serverUuid, 0)).model_dump()}


@app.post("/api/orchestrator/clusters/{clusterUuid}/remove")
def RemoveCluster(clusterUuid: UUID) -> Dict[str, Any]:
    svc = _get_services()
    try:
        svc.RemoveCluster(clusterUuid)
    except KeyError:
        raise HTTPException(status_code=404, detail="cluster not found")

    _try_save_state(svc)
    return {"ok": True}


# -----------------------------------------------------------------------------
# Config bundles
# -----------------------------------------------------------------------------

class ConfigBundleCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    tags: List[str] = []
    content: Optional[Dict[str, Any]] = None


class ConfigBundleFromClusterRequest(BaseModel):
    clusterUuid: UUID
    name: str
    description: Optional[str] = None
    tags: List[str] = []


class ConfigBundleUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    content: Optional[Dict[str, Any]] = None


class ApplyConfigRequest(BaseModel):
    clusterUuid: Optional[UUID] = None
    clusterUuids: List[UUID] = []
    dryRun: bool = False


def _config_counts(content: Dict[str, Any]) -> Dict[str, int]:
    def _count(key: str) -> int:
        items = content.get(key, [])
        if isinstance(items, list):
            return len(items)
        return 0

    return {
        "actions": _count("actions"),
        "conditions": _count("conditions"),
        "triggers": _count("triggers"),
    }


def _config_content_dict(record: Any) -> Dict[str, Any]:
    raw = getattr(record, "content", None)
    if isinstance(raw, dict):
        return dict(raw)
    return {}


def _config_meta_dict(record: Any) -> Dict[str, Any]:
    content = _config_content_dict(record)
    counts = _config_counts(content)
    return {
        "uuid": str(record.uuid),
        "name": record.name,
        "description": record.description,
        "tags": list(record.tags),
        "revision": int(record.revision),
        "createdAtUnix": float(record.createdAtUnix),
        "updatedAtUnix": float(record.updatedAtUnix),
        "sourceClusterUuid": (None if record.sourceClusterUuid is None else str(record.sourceClusterUuid)),
        "counts": counts,
    }


def _config_full_dict(record: Any) -> Dict[str, Any]:
    payload = _config_meta_dict(record)
    payload["content"] = _config_content_dict(record)
    return payload


@app.get("/api/orchestrator/configs")
def ListConfigBundles() -> Dict[str, Any]:
    svc = _get_services()
    configs = svc.ListConfigBundles()
    return {"configs": [_config_meta_dict(c) for c in configs]}


@app.get("/api/orchestrator/configs/{configUuid}")
def GetConfigBundle(configUuid: UUID) -> Dict[str, Any]:
    svc = _get_services()
    record = svc.GetConfigBundle(configUuid)
    if record is None:
        raise HTTPException(status_code=404, detail="config bundle not found")
    return {"config": _config_full_dict(record)}


@app.post("/api/orchestrator/configs/create")
def CreateConfigBundle(req: ConfigBundleCreateRequest) -> Dict[str, Any]:
    svc = _get_services()
    try:
        record = svc.CreateConfigBundle(
            name=req.name,
            description=req.description,
            tags=req.tags,
            content=req.content,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    _try_save_state(svc)
    return {"ok": True, "config": _config_full_dict(record)}


@app.post("/api/orchestrator/configs/from_cluster")
async def CreateConfigBundleFromCluster(req: ConfigBundleFromClusterRequest) -> Dict[str, Any]:
    svc = _get_services()
    base = _require_cluster_base_url(svc, req.clusterUuid)
    state_any = await _proxy_json("GET", base, "/api/state/export")
    if not isinstance(state_any, dict):
        raise HTTPException(status_code=502, detail="cluster /api/state/export returned invalid payload")

    actions = state_any.get("actions", [])
    conditions = state_any.get("conditions", [])
    triggers = state_any.get("triggers", [])
    content = {
        "version": 1,
        "actions": list(actions) if isinstance(actions, list) else [],
        "conditions": list(conditions) if isinstance(conditions, list) else [],
        "triggers": list(triggers) if isinstance(triggers, list) else [],
    }

    try:
        record = svc.CreateConfigBundle(
            name=req.name,
            description=req.description,
            tags=req.tags,
            content=content,
            sourceClusterUuid=req.clusterUuid,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    _try_save_state(svc)
    return {"ok": True, "config": _config_full_dict(record)}


@app.post("/api/orchestrator/configs/{configUuid}/update")
def UpdateConfigBundle(configUuid: UUID, req: ConfigBundleUpdateRequest) -> Dict[str, Any]:
    svc = _get_services()
    try:
        record = svc.UpdateConfigBundle(
            configUuid,
            name=req.name,
            description=req.description,
            tags=req.tags,
            content=req.content,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="config bundle not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    _try_save_state(svc)
    return {"ok": True, "config": _config_full_dict(record)}


@app.post("/api/orchestrator/configs/{configUuid}/remove")
def RemoveConfigBundle(configUuid: UUID) -> Dict[str, Any]:
    svc = _get_services()
    try:
        svc.RemoveConfigBundle(configUuid)
    except KeyError:
        raise HTTPException(status_code=404, detail="config bundle not found")

    _try_save_state(svc)
    return {"ok": True}


@app.get("/api/orchestrator/configs/assignments")
def ListConfigAssignments() -> Dict[str, Any]:
    svc = _get_services()
    assignments = svc.ListConfigAssignments()
    clusters = {c.uuid: c for c in svc.ListClusters(includeDecommissioned=True)}
    configs = {c.uuid: c for c in svc.ListConfigBundles()}
    items: List[Dict[str, Any]] = []
    for a in assignments:
        cluster = clusters.get(a.clusterUuid)
        config = configs.get(a.configUuid)
        is_stale = False
        if config is not None:
            is_stale = int(a.configRevision) != int(config.revision)
        items.append(
            {
                "clusterUuid": str(a.clusterUuid),
                "clusterLabel": (None if cluster is None else cluster.label),
                "configUuid": str(a.configUuid),
                "configName": (None if config is None else config.name),
                "configRevision": int(a.configRevision),
                "assignedAtUnix": float(a.assignedAtUnix),
                "isStale": bool(is_stale),
            }
        )
    return {"assignments": items}


@app.post("/api/orchestrator/configs/{configUuid}/apply")
async def ApplyConfigBundle(configUuid: UUID, req: ApplyConfigRequest) -> Dict[str, Any]:
    svc = _get_services()
    config = svc.GetConfigBundle(configUuid)
    if config is None:
        raise HTTPException(status_code=404, detail="config bundle not found")

    targets: List[UUID] = []
    if req.clusterUuid is not None:
        targets.append(req.clusterUuid)
    if req.clusterUuids:
        targets.extend(req.clusterUuids)
    if not targets:
        raise HTTPException(status_code=400, detail="clusterUuid or clusterUuids is required")

    content = _config_content_dict(config)
    counts = _config_counts(content)
    seen: set = set()
    results: List[Dict[str, Any]] = []

    for cluster_uuid in targets:
        if cluster_uuid in seen:
            continue
        seen.add(cluster_uuid)

        if svc.GetCluster(cluster_uuid) is None:
            raise HTTPException(status_code=404, detail=f"cluster not found: {cluster_uuid}")

        if req.dryRun:
            results.append(
                {
                    "clusterUuid": str(cluster_uuid),
                    "dryRun": True,
                    "counts": counts,
                }
            )
            continue

        base = _require_cluster_base_url(svc, cluster_uuid)
        defaults_any = await _proxy_json("GET", base, "/api/app/defaults")
        if not isinstance(defaults_any, dict):
            raise HTTPException(status_code=502, detail="cluster /api/app/defaults returned invalid payload")

        state_payload = {
            "version": 1,
            "savedAtUnix": float(time.time()),
            "app": defaults_any,
            "actions": list(content.get("actions", [])) if isinstance(content.get("actions", []), list) else [],
            "conditions": list(content.get("conditions", [])) if isinstance(content.get("conditions", []), list) else [],
            "triggers": list(content.get("triggers", [])) if isinstance(content.get("triggers", []), list) else [],
        }

        await _proxy_json(
            "POST",
            base,
            "/api/state/import",
            body={"state": state_payload, "keepServerUuid": True},
        )
        svc.AssignConfigBundle(cluster_uuid, configUuid)
        results.append({"clusterUuid": str(cluster_uuid), "applied": True, "counts": counts})

    if not req.dryRun:
        _try_save_state(svc)
    return {"ok": True, "results": results}


# -----------------------------------------------------------------------------
# Screens (layouts + assignments)
# -----------------------------------------------------------------------------

class DisplayScreenDto(BaseModel):
    label: str
    left: int
    top: int
    width: int
    height: int


class DisplayLayoutCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    screens: List[DisplayScreenDto] = []


class DisplayLayoutUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    screens: Optional[List[DisplayScreenDto]] = None


class DisplayAssignmentRequest(BaseModel):
    clusterUuid: UUID
    layoutUuid: UUID
    screenLabel: str


class DisplayUnassignRequest(BaseModel):
    clusterUuid: UUID


class DisplayApplyRequest(BaseModel):
    clusterUuid: Optional[UUID] = None
    clusterUuids: List[UUID] = []
    applyAll: bool = False
    dryRun: bool = False
    windowTitle: Optional[str] = None


def _screen_dict(screen: Any) -> Dict[str, Any]:
    return {
        "label": str(screen.label),
        "left": int(screen.left),
        "top": int(screen.top),
        "width": int(screen.width),
        "height": int(screen.height),
    }


def _layout_dict(record: Any, includeScreens: bool = False) -> Dict[str, Any]:
    payload = {
        "uuid": str(record.uuid),
        "name": str(record.name),
        "description": str(record.description),
        "screenLabels": [s.label for s in record.screens],
        "screenCount": len(record.screens),
        "createdAtUnix": float(record.createdAtUnix),
        "updatedAtUnix": float(record.updatedAtUnix),
    }
    if includeScreens:
        payload["screens"] = [_screen_dict(s) for s in record.screens]
    return payload


@app.get("/api/orchestrator/screens/layouts")
def ListDisplayLayouts() -> Dict[str, Any]:
    svc = _get_services()
    layouts = svc.ListDisplayLayouts()
    return {"layouts": [_layout_dict(l) for l in layouts]}


@app.get("/api/orchestrator/screens/layouts/{layoutUuid}")
def GetDisplayLayout(layoutUuid: UUID) -> Dict[str, Any]:
    svc = _get_services()
    record = svc.GetDisplayLayout(layoutUuid)
    if record is None:
        raise HTTPException(status_code=404, detail="layout not found")
    return {"layout": _layout_dict(record, includeScreens=True)}


@app.post("/api/orchestrator/screens/layouts/create")
def CreateDisplayLayout(req: DisplayLayoutCreateRequest) -> Dict[str, Any]:
    svc = _get_services()
    try:
        record = svc.CreateDisplayLayout(
            name=req.name,
            description=req.description,
            screens=[s.model_dump() for s in (req.screens or [])],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    _try_save_state(svc)
    return {"ok": True, "layout": _layout_dict(record, includeScreens=True)}


@app.post("/api/orchestrator/screens/layouts/{layoutUuid}/update")
def UpdateDisplayLayout(layoutUuid: UUID, req: DisplayLayoutUpdateRequest) -> Dict[str, Any]:
    svc = _get_services()
    screens = None
    if req.screens is not None:
        screens = [s.model_dump() for s in req.screens]

    try:
        record = svc.UpdateDisplayLayout(
            layoutUuid,
            name=req.name,
            description=req.description,
            screens=screens,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="layout not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    _try_save_state(svc)
    return {"ok": True, "layout": _layout_dict(record, includeScreens=True)}


@app.post("/api/orchestrator/screens/layouts/{layoutUuid}/remove")
def RemoveDisplayLayout(layoutUuid: UUID) -> Dict[str, Any]:
    svc = _get_services()
    try:
        svc.RemoveDisplayLayout(layoutUuid)
    except KeyError:
        raise HTTPException(status_code=404, detail="layout not found")

    _try_save_state(svc)
    return {"ok": True}


@app.get("/api/orchestrator/screens/assignments")
def ListDisplayAssignments() -> Dict[str, Any]:
    svc = _get_services()
    assignments = svc.ListDisplayAssignments()
    clusters = {c.uuid: c for c in svc.ListClusters(includeDecommissioned=True)}
    layouts = {l.uuid: l for l in svc.ListDisplayLayouts()}

    items: List[Dict[str, Any]] = []
    for a in assignments:
        cluster = clusters.get(a.clusterUuid)
        layout = layouts.get(a.layoutUuid)
        items.append(
            {
                "clusterUuid": str(a.clusterUuid),
                "clusterLabel": (None if cluster is None else cluster.label),
                "layoutUuid": str(a.layoutUuid),
                "layoutName": (None if layout is None else layout.name),
                "screenLabel": a.screenLabel,
                "assignedAtUnix": float(a.assignedAtUnix),
            }
        )
    return {"assignments": items}


@app.post("/api/orchestrator/screens/assign")
def AssignDisplay(req: DisplayAssignmentRequest) -> Dict[str, Any]:
    svc = _get_services()
    if svc.GetCluster(req.clusterUuid) is None:
        raise HTTPException(status_code=404, detail="cluster not found")
    try:
        record = svc.AssignDisplay(req.clusterUuid, req.layoutUuid, req.screenLabel)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    _try_save_state(svc)
    return {
        "ok": True,
        "assignment": {
            "clusterUuid": str(record.clusterUuid),
            "layoutUuid": str(record.layoutUuid),
            "screenLabel": record.screenLabel,
            "assignedAtUnix": float(record.assignedAtUnix),
        },
    }


@app.post("/api/orchestrator/screens/unassign")
def UnassignDisplay(req: DisplayUnassignRequest) -> Dict[str, Any]:
    svc = _get_services()
    try:
        svc.RemoveDisplayAssignment(req.clusterUuid)
    except KeyError:
        raise HTTPException(status_code=404, detail="assignment not found")

    _try_save_state(svc)
    return {"ok": True}


@app.post("/api/orchestrator/screens/apply")
async def ApplyDisplayLayouts(req: DisplayApplyRequest) -> Dict[str, Any]:
    svc = _get_services()
    targets: List[UUID] = []
    if bool(req.applyAll):
        targets = [a.clusterUuid for a in svc.ListDisplayAssignments()]
    else:
        if req.clusterUuid is not None:
            targets.append(req.clusterUuid)
        if req.clusterUuids:
            targets.extend(req.clusterUuids)

    if not targets:
        raise HTTPException(status_code=400, detail="clusterUuid, clusterUuids, or applyAll is required")

    assignments = {a.clusterUuid: a for a in svc.ListDisplayAssignments()}
    layouts = {l.uuid: l for l in svc.ListDisplayLayouts()}

    seen: set = set()
    results: List[Dict[str, Any]] = []
    for cu in targets:
        if cu in seen:
            continue
        seen.add(cu)

        cluster = svc.GetCluster(cu)
        if cluster is None:
            results.append({"clusterUuid": str(cu), "error": "cluster not found"})
            continue

        assignment = assignments.get(cu)
        if assignment is None:
            results.append({"clusterUuid": str(cu), "error": "no display assignment"})
            continue

        layout = layouts.get(assignment.layoutUuid)
        if layout is None:
            results.append({"clusterUuid": str(cu), "error": "layout not found"})
            continue

        screen = next((s for s in layout.screens if s.label == assignment.screenLabel), None)
        if screen is None:
            results.append({"clusterUuid": str(cu), "error": "screen label not found"})
            continue

        if req.dryRun:
            results.append(
                {
                    "clusterUuid": str(cu),
                    "dryRun": True,
                    "layoutUuid": str(layout.uuid),
                    "screenLabel": screen.label,
                }
            )
            continue

        try:
            base = _require_cluster_base_url(svc, cu)
        except HTTPException as exc:
            results.append({"clusterUuid": str(cu), "error": exc.detail})
            continue

        window_title = str(req.windowTitle or "").strip()
        if not window_title:
            defaults_any = await _proxy_json("GET", base, "/api/app/defaults")
            if not isinstance(defaults_any, dict):
                results.append({"clusterUuid": str(cu), "error": "cluster /api/app/defaults returned invalid payload"})
                continue
            window_title = str(defaults_any.get("defaultWindowTitle", "") or "").strip()
        if not window_title:
            results.append({"clusterUuid": str(cu), "error": "window title is required"})
            continue

        body = {
            "window_title": window_title,
            "left": int(screen.left),
            "top": int(screen.top),
            "width": int(screen.width),
            "height": int(screen.height),
        }

        try:
            await _proxy_json("POST", base, "/api/app/attach", body=body)
            results.append(
                {
                    "clusterUuid": str(cu),
                    "layoutUuid": str(layout.uuid),
                    "screenLabel": screen.label,
                    "applied": True,
                }
            )
        except HTTPException as exc:
            results.append({"clusterUuid": str(cu), "error": exc.detail})

    if not req.dryRun:
        _try_save_state(svc)
    return {"ok": True, "results": results}


# -----------------------------------------------------------------------------
# Orchestrator state
# -----------------------------------------------------------------------------

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
# Cluster proxies
# -----------------------------------------------------------------------------


# --- Server info ---

@app.get("/api/orchestrator/clusters/{clusterUuid}/server/info")
async def ProxyServerInfo(clusterUuid: UUID) -> Any:
    svc = _get_services()
    base = _require_cluster_base_url(svc, clusterUuid)
    return await _proxy_json("GET", base, "/api/server/info")


# --- Actions (list) ---

@app.get("/api/orchestrator/clusters/{clusterUuid}/actions")
async def ProxyActionsList(clusterUuid: UUID) -> Any:
    svc = _get_services()
    base = _require_cluster_base_url(svc, clusterUuid)
    return await _proxy_json("GET", base, "/api/actions")


# --- Proxy body wrapper ---

class ProxyBodyRequest(BaseModel):
    body: Dict[str, Any]


# --- App window + capture ---

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


@app.get("/api/orchestrator/clusters/{clusterUuid}/capture/latest")
async def ProxyCaptureLatest(clusterUuid: UUID, fmt: str = "jpg") -> Response:
    svc = _get_services()
    base = _require_cluster_base_url(svc, clusterUuid)
    clean_fmt = str(fmt or "jpg").strip().lstrip(".")
    return await _proxy_bytes("GET", base, f"/api/capture/latest?fmt={clean_fmt}")


@app.get("/api/orchestrator/clusters/{clusterUuid}/capture/stream")
async def ProxyCaptureStream(clusterUuid: UUID, fmt: str = "jpg", quality: int = 70) -> StreamingResponse:
    svc = _get_services()
    base = _require_cluster_base_url(svc, clusterUuid)
    clean_fmt = str(fmt or "jpg").strip().lstrip(".")
    q = int(quality)
    q = max(10, min(95, q))
    return await _proxy_sse(base, f"/api/capture/stream?fmt={clean_fmt}&quality={q}")


# --- Actions (mutations) ---

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


@app.post("/api/orchestrator/clusters/{clusterUuid}/actions/move")
async def ProxyActionsMove(clusterUuid: UUID, req: ProxyBodyRequest) -> Any:
    svc = _get_services()
    base = _require_cluster_base_url(svc, clusterUuid)
    return await _proxy_json("POST", base, "/api/actions/move", body=dict(req.body))


@app.post("/api/orchestrator/clusters/{clusterUuid}/actions/run")
async def ProxyActionsRun(clusterUuid: UUID, req: ProxyBodyRequest) -> Any:
    svc = _get_services()
    base = _require_cluster_base_url(svc, clusterUuid)
    return await _proxy_json("POST", base, "/api/actions/run", body=dict(req.body))


# --- Conditions ---

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


# --- Triggers ---

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


@app.post("/api/orchestrator/clusters/{clusterUuid}/triggers/move")
async def ProxyTriggersMove(clusterUuid: UUID, req: ProxyBodyRequest) -> Any:
    svc = _get_services()
    base = _require_cluster_base_url(svc, clusterUuid)
    return await _proxy_json("POST", base, "/api/triggers/move", body=dict(req.body))


@app.post("/api/orchestrator/clusters/{clusterUuid}/triggers/set_enabled")
async def ProxyTriggersSetEnabled(clusterUuid: UUID, req: ProxyBodyRequest) -> Any:
    svc = _get_services()
    base = _require_cluster_base_url(svc, clusterUuid)
    return await _proxy_json("POST", base, "/api/triggers/set_enabled", body=dict(req.body))
