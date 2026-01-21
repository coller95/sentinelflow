from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Dict, List, Optional, cast
from urllib.parse import urljoin
from uuid import UUID, uuid4

import cv2
import numpy as np
import httpx
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response, StreamingResponse

from .services import OrchestratorServices, ClusterRecord
from .models import (
    ActionItemDto, ActionMoveRequest, ActionRunRequest, ActionUpsertRequest, ActionUuidRequest,
    ApplyConfigRequest, AutomationStateImportRequest, ClusterItemDto, CommissionClusterFromUrlRequest,
    CommissionClusterRequest, ConditionItemDto, ConditionMoveRequest, ConditionRoiDto,
    ConditionSetFromLiveRequest, ConditionTypeDto, ConditionUpsertRequest, ConditionUuidRequest,
    ConfigBundleCreateRequest, ConfigBundleFromClusterRequest, ConfigBundleUpdateRequest,
    DisplayApplyRequest, DisplayAssignmentRequest, DisplayLayoutCreateRequest, DisplayLayoutUpdateRequest,
    DisplayUnassignRequest, MacroStepDto, MacroTypeDto, OrchestratorImportRequest,
    ProxyBodyRequest, TriggerCiteriaDto, TriggerComparatorDto, TriggerCriteriaModeDto, TriggerItemDto,
    TriggerMoveRequest, TriggerSetEnabledRequest, TriggerUpsertRequest, TriggerUuidRequest, UpdateClusterRequest
)
from .utils import (
    crop_frame_normalized, decode_image_b64, default_label_from_base_url, encode_jpeg_b64, encode_png_b64,
    find_item_index, normalize_base_url, resource_root, state_root
)


app = FastAPI()

httpx_async_client: Optional[httpx.AsyncClient] = None
_monitor_client: Optional[httpx.AsyncClient] = None
_cluster_monitor_task: Optional[asyncio.Task[Any]] = None
_stop_event: Optional[asyncio.Event] = None
# Condition variable to broadcast automation config changes to SSE listeners
_automation_cond: Optional[asyncio.Condition] = None

@app.on_event("startup")
async def startup_event():
    global httpx_async_client, _monitor_client, _cluster_monitor_task, _stop_event
    _stop_event = asyncio.Event()
    app.state.automation_cond = asyncio.Condition()
    
    # 1. Main Client (User/UI Proxy) - High concurrency, standard timeouts
    limits = httpx.Limits(max_keepalive_connections=20, max_connections=100)
    timeout = httpx.Timeout(connect=5.0, read=30.0, write=30.0, pool=5.0)
    httpx_async_client = httpx.AsyncClient(limits=limits, timeout=timeout)
    
    # 2. Monitor Client (Background Health) - Low concurrency, strict fail-fast timeouts
    # We use a separate pool so background checks never starve UI requests.
    mon_limits = httpx.Limits(max_keepalive_connections=0, max_connections=20)
    mon_timeout = httpx.Timeout(connect=2.0, read=2.0, write=2.0, pool=1.0)
    _monitor_client = httpx.AsyncClient(limits=mon_limits, timeout=mon_timeout)
    
    _cluster_monitor_task = asyncio.create_task(_monitor_clusters())

@app.on_event("shutdown")
async def shutdown_event():
    global httpx_async_client, _cluster_monitor_task, _stop_event
    if _stop_event:
        _stop_event.set()
    if _cluster_monitor_task:
        _cluster_monitor_task.cancel()
        try:
            await _cluster_monitor_task
        except asyncio.CancelledError:
            pass
    if httpx_async_client:
        await httpx_async_client.aclose()
    if _monitor_client:
        await _monitor_client.aclose()


async def _monitor_clusters():
    """Background task to poll clusters for health/online status."""
    svc = _get_services()
    # Limit concurrent health checks to avoid flooding the loop/DNS
    sem = asyncio.Semaphore(20)

    while svc.IsRunning():
        try:
            # Wait for 5s or until shutdown event
            if _stop_event:
                try:
                    await asyncio.wait_for(_stop_event.wait(), timeout=5.0)
                    break
                except asyncio.TimeoutError:
                    pass
            else:
                await asyncio.sleep(5)
            
            if not svc.IsRunning():
                break

            clusters = svc.ListClusters(includeDecommissioned=False)
            
            # Use gather with semaphore-limited wrappers
            async def _bounded_check(c_uuid: UUID, c_url: str):
                async with sem:
                    await _check_cluster_health(svc, c_uuid, c_url)

            tasks: List[asyncio.Task[None]] = []
            for c in clusters:
                base = (c.baseUrl or "").strip()
                if not base:
                    continue
                if not (base.startswith("http://") or base.startswith("https://")):
                    base = "http://" + base
                if not base.endswith("/"):
                    base += "/"
                
                url = urljoin(base, "api/server/info")
                tasks.append(asyncio.create_task(_bounded_check(c.uuid, url)))
            
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[_monitor_clusters] error: {e}")
            await asyncio.sleep(5)

async def _check_cluster_health(svc: OrchestratorServices, cluster_uuid: UUID, url: str):
    global _monitor_client
    if not _monitor_client:
        return
    try:
        resp = await _monitor_client.get(url)
        if resp.status_code == 200:
            svc.UpdateClusterLastSeen(cluster_uuid, time.time())
    except Exception:
        pass



# -----------------------------------------------------------------------------
# Runtime paths + persistence
# -----------------------------------------------------------------------------

_public_dir = resource_root() / "web" / "orchestrator"
_cluster_public_dir = resource_root() / "web" / "cluster"
app.mount("/static", StaticFiles(directory=str(_public_dir)), name="static")
app.mount("/cluster-static", StaticFiles(directory=str(_cluster_public_dir)), name="cluster-static")


_STATE_PATH = state_root() / "orchestrator_state.json"


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

def _ensure_automation_config(svc: OrchestratorServices) -> None:
    before = svc.GetAutomationConfigUuid()
    config = svc.EnsureAutomationConfig()
    if before != config.uuid:
        _try_save_state(svc)


def _get_services() -> OrchestratorServices:
    svc = getattr(app.state, "services", None)
    if svc is not None:
        if not bool(getattr(app.state, "stateLoaded", False)):
            _try_load_state(svc)
            _ensure_automation_config(svc)
            app.state.stateLoaded = True
        return svc

    # Fallback: create lazily.
    svc = OrchestratorServices()
    _try_load_state(svc)
    _ensure_automation_config(svc)
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


@app.get("/automation")
def GetAutomationUi() -> FileResponse:
    ui_path = _public_dir / "automation.html"
    return FileResponse(str(ui_path), media_type="text/html")


# -----------------------------------------------------------------------------
# Cluster proxy helpers
# -----------------------------------------------------------------------------

def _require_cluster_base_url(
    svc: OrchestratorServices,
    clusterUuid: UUID,
    allowDuplicates: bool = False,
) -> str:
    record = svc.GetCluster(clusterUuid)
    if record is None:
        raise HTTPException(status_code=404, detail="cluster not found")

    if not allowDuplicates:
        dupes = svc.FindClustersByServerUuid(record.uuid, includeDecommissioned=False)
        if len(dupes) > 1:
            base_urls = [str(c.baseUrl or "") for c in dupes if c.baseUrl]
            suffix = f" ({', '.join(base_urls)})" if base_urls else ""
            raise HTTPException(
                status_code=409,
                detail=f"duplicate cluster UUID detected; resolve duplicates before proxying{suffix}",
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
    try:
        global httpx_async_client
        if httpx_async_client:
             res = await httpx_async_client.request(method.upper(), url, json=body)
        else:
             async with httpx.AsyncClient(timeout=30.0) as client:
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
                    payload: Dict[str, Any] = cast(Dict[str, Any], payload_any)
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
    try:
        global httpx_async_client
        if httpx_async_client:
            res = await httpx_async_client.request(method.upper(), url)
        else:
            async with httpx.AsyncClient(timeout=30.0) as client:
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
                    payload: Dict[str, Any] = cast(Dict[str, Any], payload_any)
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


@app.websocket("/api/orchestrator/cctv/ws")
async def CctvWebSocket(websocket: WebSocket):
    await websocket.accept()
    svc = _get_services()
    active_uuids: List[UUID] = []
    
    try:
        # We use a simple protocol:
        # Client sends JSON: ["uuid1", "uuid2", ...] (list of subscribed clusters)
        # Server sends JSON: [{"uuid": "...", "b64": "..."}, ...] (list of updates)
        
        async def receive_loop():
            nonlocal active_uuids
            try:
                while True:
                    data = await websocket.receive_json()
                    if isinstance(data, list):
                        new_list: List[UUID] = []
                        for s in data:
                            try:
                                new_list.append(UUID(str(s)))
                            except Exception:
                                pass
                        active_uuids = new_list
            except WebSocketDisconnect:
                pass
            except Exception as e:
                print(f"[CCTV WS] Receive error: {e}")

        async def send_loop():
            nonlocal active_uuids
            while True:
                if not active_uuids:
                    await asyncio.sleep(0.5)
                    continue
                
                # Snapshot current list to avoid modification during iteration
                current_targets = list(active_uuids)
                
                # Fetch all frames concurrently
                tasks = []
                for cu in current_targets:
                    tasks.append(_fetch_cluster_latest_frame(svc, cu))
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                updates = []
                for i, res in enumerate(results):
                    if isinstance(res, np.ndarray):
                        b64 = encode_jpeg_b64(res, quality=70)
                        if b64:
                            updates.append({
                                "uuid": str(current_targets[i]),
                                "b64": b64
                            })
                
                if updates:
                    try:
                        await websocket.send_json(updates)
                    except Exception:
                        break # Socket likely closed
                
                await asyncio.sleep(0.5) # Throttle to ~2 FPS per camera for grid view

        # Run both loops
        receiver = asyncio.create_task(receive_loop())
        sender = asyncio.create_task(send_loop())
        
        done, pending = await asyncio.wait(
            [receiver, sender],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for t in pending:
            t.cancel()
            
    except Exception as e:
        print(f"[CCTV WS] Error: {e}")
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


# -----------------------------------------------------------------------------
# Cluster management models
# -----------------------------------------------------------------------------







def _to_dto(record: Any, duplicate_count: int = 0) -> ClusterItemDto:
    return ClusterItemDto(
        uuid=str(record.uuid),
        serverUuid=str(record.serverUuid),
        label=record.label,
        baseUrl=record.baseUrl,
        commissionedAtUnix=float(record.commissionedAtUnix),
        decommissionedAtUnix=(None if record.decommissionedAtUnix is None else float(record.decommissionedAtUnix)),
        duplicateCount=int(duplicate_count),
        isDuplicate=bool(duplicate_count > 1),
    )


def _duplicate_server_uuid_counts(clusters: list[Any]) -> Dict[UUID, int]:
    counts: Dict[UUID, int] = {}
    for c in clusters:
        if c is None:
            continue
        if getattr(c, "decommissionedAtUnix", None) is not None:
            continue
        cu = getattr(c, "uuid", None)
        if cu is None:
            continue
        counts[cu] = counts.get(cu, 0) + 1
    return counts




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
    return {"ok": True, "cluster": _to_dto(record, dup_counts.get(record.uuid, 0)).model_dump()}


@app.post("/api/orchestrator/clusters/commission_from_url")
async def CommissionClusterFromUrl(req: CommissionClusterFromUrlRequest) -> Dict[str, Any]:
    svc = _get_services()
    try:
        base_url = normalize_base_url(req.baseUrl)
        label = str(req.label or "").strip() or default_label_from_base_url(base_url)
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

    if base_url:
        svc.UpdateClustersServerUuidByBaseUrl(base_url, server_uuid)
        record = svc.GetCluster(server_uuid) or record
    dup_counts = _duplicate_server_uuid_counts(svc.ListClusters(includeDecommissioned=True))
    _try_save_state(svc)
    return {
        "ok": True,
        "cluster": _to_dto(record, dup_counts.get(record.uuid, 0)).model_dump(),
        "discovered": {"serverUuid": str(server_uuid)},
    }


@app.get("/api/orchestrator/clusters")
async def ListClusters(includeDecommissioned: bool = False, refreshServerUuid: bool = True) -> Dict[str, Any]:
    svc = _get_services()
    clusters = svc.ListClusters(includeDecommissioned=bool(includeDecommissioned))

    dup_counts = _duplicate_server_uuid_counts(clusters)
    return {"clusters": [_to_dto(c, dup_counts.get(c.uuid, 0)).model_dump() for c in clusters]}


@app.get("/api/orchestrator/clusters/{clusterUuid}")
def GetCluster(clusterUuid: UUID) -> Dict[str, Any]:
    svc = _get_services()
    record = svc.GetCluster(clusterUuid)
    if record is None:
        raise HTTPException(status_code=404, detail="cluster not found")
    dup_counts = _duplicate_server_uuid_counts(svc.ListClusters(includeDecommissioned=True))
    return {"cluster": _to_dto(record, dup_counts.get(record.uuid, 0)).model_dump()}


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
        base_url = normalize_base_url(raw) if raw else None

    try:
        record = svc.UpdateCluster(clusterUuid, label=label, baseUrl=base_url)
    except KeyError:
        raise HTTPException(status_code=404, detail="cluster not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    dup_counts = _duplicate_server_uuid_counts(svc.ListClusters(includeDecommissioned=True))
    _try_save_state(svc)
    return {"ok": True, "cluster": _to_dto(record, dup_counts.get(record.uuid, 0)).model_dump()}


@app.post("/api/orchestrator/clusters/{clusterUuid}/decommission")
def DecommissionCluster(clusterUuid: UUID) -> Dict[str, Any]:
    svc = _get_services()
    try:
        record = svc.DecommissionCluster(clusterUuid)
    except KeyError:
        raise HTTPException(status_code=404, detail="cluster not found")

    dup_counts = _duplicate_server_uuid_counts(svc.ListClusters(includeDecommissioned=True))
    _try_save_state(svc)
    return {"ok": True, "cluster": _to_dto(record, dup_counts.get(record.uuid, 0)).model_dump()}


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



# -----------------------------------------------------------------------------
# Automation (global: orchestrator-managed actions/conditions/triggers)
# -----------------------------------------------------------------------------





def _config_counts(content: Dict[str, Any]) -> Dict[str, int]:
    def _count(key: str) -> int:
        items = content.get(key, [])
        if isinstance(items, list):
            return len(cast(List[Any], items))
        return 0

    return {
        "actions": _count("actions"),
        "conditions": _count("conditions"),
        "triggers": _count("triggers"),
    }


def _config_content_dict(record: Any) -> Dict[str, Any]:
    raw = getattr(record, "content", None)
    if isinstance(raw, dict):
        return cast(Dict[str, Any], raw)
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

    state_dict = cast(Dict[str, Any], state_any)
    actions: Any = state_dict.get("actions", [])
    conditions: Any = state_dict.get("conditions", [])
    triggers: Any = state_dict.get("triggers", [])
    content: Dict[str, Any] = {
        "version": 1,
        "actions": list(cast(List[Any], actions)),
        "conditions": list(cast(List[Any], conditions)),
        "triggers": list(cast(List[Any], triggers)),
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
    seen: set[UUID] = set()
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

        state_payload: Dict[str, Any] = {
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
# Automation (global)
# -----------------------------------------------------------------------------

def _normalize_automation_content(content: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(content, dict):
        content = {}

    seeded = bool(content.get("seeded", False))
    app = content.get("app", {})
    if not isinstance(app, dict):
        app = {}

    def _list(key: str) -> List[Any]:
        raw = content.get(key, [])
        if isinstance(raw, list):
            return list(raw)
        return []

    return {
        "version": 1,
        "seeded": seeded,
        "app": dict(app),
        "actions": _list("actions"),
        "conditions": _list("conditions"),
        "triggers": _list("triggers"),
    }


def _seed_automation_content(content: Dict[str, Any]) -> Dict[str, Any]:
    if content.get("seeded"):
        return content
    if content.get("actions") or content.get("conditions") or content.get("triggers"):
        return content

    action_uuid = str(uuid4())
    condition_uuid = str(uuid4())
    trigger_uuid = str(uuid4())

    seeded = dict(content)
    seeded["seeded"] = True
    seeded["actions"] = [
        {
            "uuid": action_uuid,
            "name": "Sample Action",
            "steps": [
                {"action": "Delay", "parameters": {"ms": 250}},
            ],
        }
    ]
    seeded["conditions"] = [
        {
            "uuid": condition_uuid,
            "name": "Sample Condition",
            "type": "ImageMatchRoi",
            "roi": {
                "xNormalized": 0.1,
                "yNormalized": 0.1,
                "widthNormalized": 0.1,
                "heightNormalized": 0.1,
            },
        }
    ]
    seeded["triggers"] = [
        {
            "uuid": trigger_uuid,
            "name": "Sample Trigger",
            "enabled": False,
            "retriggerMs": 0,
            "disableOnFire": False,
            "criteriaMode": "All",
            "action": action_uuid,
            "triggerCiterias": [
                {
                    "conditionUuid": condition_uuid,
                    "comparator": "GreaterThanOrEqual",
                    "expectedValue": 0.9,
                }
            ],
        }
    ]
    return seeded


def _get_automation_content(svc: OrchestratorServices) -> Dict[str, Any]:
    config = svc.EnsureAutomationConfig()
    content = _normalize_automation_content(getattr(config, "content", None))
    seeded = _seed_automation_content(content)
    if seeded is not content:
        _update_automation_content(svc, seeded)
        return seeded
    return content


async def _notify_automation_change():
    print("[Orchestrator] Notifying automation change...")
    cond = getattr(app.state, "automation_cond", None)
    if cond:
        async with cond:
            cond.notify_all()

def _update_automation_content(svc: OrchestratorServices, content: Dict[str, Any]) -> Any:

    config = svc.EnsureAutomationConfig()

    record = svc.UpdateConfigBundle(config.uuid, content=content)

    _try_save_state(svc)

    return record





async def _fetch_cluster_latest_frame(svc: OrchestratorServices, clusterUuid: UUID) -> Optional[np.ndarray]:
    try:
        base = _require_cluster_base_url(svc, clusterUuid)
    except HTTPException:
        return None

    url = urljoin(base, "/api/capture/latest?fmt=png")
    try:
        global httpx_async_client
        if httpx_async_client:
            res = await httpx_async_client.get(url)
        else:
             async with httpx.AsyncClient(timeout=10.0) as client:
                 res = await client.get(url)
    except httpx.RequestError:
        return None
    if res.status_code >= 400:
        return None
    arr = np.frombuffer(res.content, dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


async def _push_automation_to_clusters(svc: OrchestratorServices, content: Dict[str, Any]) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    clusters = svc.ListClusters(includeDecommissioned=False)
    config = svc.EnsureAutomationConfig()
    for cluster in clusters:
        cu = cluster.uuid
        try:
            base = _require_cluster_base_url(svc, cu)
            defaults_any = content.get("app", None)
            if not isinstance(defaults_any, dict) or not defaults_any:
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
            svc.AssignConfigBundle(cu, config.uuid)
            results.append({"clusterUuid": str(cu), "ok": True})
        except HTTPException as exc:
            results.append({"clusterUuid": str(cu), "ok": False, "error": exc.detail})
        except Exception as exc:
            results.append({"clusterUuid": str(cu), "ok": False, "error": str(exc)})

    _try_save_state(svc)
    return results


def _automation_state_payload(content: Dict[str, Any]) -> Dict[str, Any]:
    app = content.get("app", {})
    if not isinstance(app, dict):
        app = {}
    return {
        "version": 1,
        "savedAtUnix": float(time.time()),
        "app": dict(cast(Dict[str, Any], app)),
        "actions": list(cast(List[Any], content.get("actions", []))) if isinstance(content.get("actions", []), list) else [],
        "conditions": list(cast(List[Any], content.get("conditions", []))) if isinstance(content.get("conditions", []), list) else [],
        "triggers": list(cast(List[Any], content.get("triggers", []))) if isinstance(content.get("triggers", []), list) else [],
    }


async def _push_automation_to_cluster(
    svc: OrchestratorServices,
    content: Dict[str, Any],
    clusterUuid: UUID,
) -> Dict[str, Any]:
    config = svc.EnsureAutomationConfig()
    try:
        base = _require_cluster_base_url(svc, clusterUuid)
        defaults_any = content.get("app", None)
        if not isinstance(defaults_any, dict) or not defaults_any:
            defaults_any = await _proxy_json("GET", base, "/api/app/defaults")
        if not isinstance(defaults_any, dict):
            raise HTTPException(status_code=502, detail="cluster /api/app/defaults returned invalid payload")

        state_payload: Dict[str, Any] = {
            "version": 1,
            "savedAtUnix": float(time.time()),
            "app": defaults_any,
            "actions": list(cast(List[Any], content.get("actions", []))),
            "conditions": list(cast(List[Any], content.get("conditions", []))),
            "triggers": list(cast(List[Any], content.get("triggers", []))),
        }
        await _proxy_json(
            "POST",
            base,
            "/api/state/import",
            body={"state": state_payload, "keepServerUuid": True},
        )
        svc.AssignConfigBundle(clusterUuid, config.uuid)
        _try_save_state(svc)
        return {"clusterUuid": str(clusterUuid), "ok": True}
    except HTTPException as exc:
        return {"clusterUuid": str(clusterUuid), "ok": False, "error": exc.detail}
    except Exception as exc:
        return {"clusterUuid": str(clusterUuid), "ok": False, "error": str(exc)}


@app.get("/api/orchestrator/automation/state/path")
def GetAutomationStatePath() -> Dict[str, Any]:
    return {"path": str(_STATE_PATH)}


@app.get("/api/orchestrator/automation/state/export")
def ExportAutomationState(includeServerUuid: bool = False) -> Dict[str, Any]:
    svc = _get_services()
    content = _get_automation_content(svc)
    return _automation_state_payload(content)


@app.post("/api/orchestrator/automation/state/import")
async def ImportAutomationState(req: AutomationStateImportRequest) -> Dict[str, Any]:
    svc = _get_services()
    raw_state = req.state
    content = _get_automation_content(svc)
    app_any = raw_state.get("app", {})
    content["app"] = dict(app_any) if isinstance(app_any, dict) else {}
    actions = raw_state.get("actions", [])
    conditions = raw_state.get("conditions", [])
    triggers = raw_state.get("triggers", [])
    content["actions"] = list(actions) if isinstance(actions, list) else []
    content["conditions"] = list(conditions) if isinstance(conditions, list) else []
    content["triggers"] = list(triggers) if isinstance(triggers, list) else []
    _update_automation_content(svc, content)
    results = await _push_automation_to_clusters(svc, content)
    return {"ok": True, "results": results}


@app.post("/api/orchestrator/automation/state/reload")
def ReloadAutomationState() -> Dict[str, Any]:
    svc = _get_services()
    try:
        svc.LoadState(_STATE_PATH)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="orchestrator_state.json not found")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Reload failed: {exc}")

    _ensure_automation_config(svc)
    try:
        app.state.stateLoaded = True
    except Exception:
        pass

    return {"ok": True, "orchestratorUuid": str(svc.GetOrchestratorUuid())}


@app.get("/api/orchestrator/automation/actions")
def GetAutomationActions() -> List[ActionItemDto]:
    svc = _get_services()
    content = _get_automation_content(svc)
    items: List[ActionItemDto] = []
    actions_list = cast(List[Any], content.get("actions", []))
    for item_any in actions_list:
        if not isinstance(item_any, dict):
            continue
        item: Dict[str, Any] = cast(Dict[str, Any], item_any)
        steps_any = item.get("steps", [])
        steps: List[MacroStepDto] = []
        if isinstance(steps_any, list):
            for s_any in cast(List[Any], steps_any):
                if not isinstance(s_any, dict):
                    continue
                s: Dict[str, Any] = cast(Dict[str, Any], s_any)
                action_raw = str(s.get("action", "") or "").strip()
                try:
                    action = MacroTypeDto(action_raw)
                except Exception:
                    continue
                params = s.get("parameters", {})
                if not isinstance(params, dict):
                    params = {}
                steps.append(MacroStepDto(action=action, parameters=dict(cast(Dict[str, Any], params))))
        items.append(ActionItemDto(uuid=str(item.get("uuid", "")), name=str(item.get("name", "")), steps=steps))
    return items


@app.post("/api/orchestrator/automation/actions/upsert")
async def UpsertAutomationAction(req: ActionUpsertRequest) -> Dict[str, Any]:
    svc = _get_services()
    name = (req.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name cannot be empty")

    content = _get_automation_content(svc)
    actions_any = content.get("actions", [])
    actions: List[Dict[str, Any]] = list(actions_any) if isinstance(actions_any, list) else []

    action_uuid = str(req.uuid) if req.uuid is not None else str(uuid4())

    steps: List[Dict[str, Any]] = []
    for s in req.steps or []:
        steps.append({"action": s.action.value, "parameters": dict(s.parameters or {})})

    new_item = {"uuid": action_uuid, "name": name, "steps": steps}
    idx = find_item_index(actions, action_uuid)
    if idx >= 0:
        actions[idx] = new_item
    else:
        actions.append(new_item)

    content["actions"] = actions
    _update_automation_content(svc, content)
    await _notify_automation_change()
    results = await _push_automation_to_clusters(svc, content)
    return {"ok": True, "uuid": action_uuid, "results": results}


@app.post("/api/orchestrator/automation/actions/remove_uuid")
async def RemoveAutomationAction(req: ActionUuidRequest) -> Dict[str, Any]:
    svc = _get_services()
    content = _get_automation_content(svc)
    actions_any = content.get("actions", [])
    actions: List[Dict[str, Any]] = list(actions_any) if isinstance(actions_any, list) else []
    uuid_str = str(req.uuid)
    idx = find_item_index(actions, uuid_str)
    if idx < 0:
        raise HTTPException(status_code=404, detail="Action uuid not found")
    actions.pop(idx)
    content["actions"] = actions
    _update_automation_content(svc, content)
    await _notify_automation_change()
    results = await _push_automation_to_clusters(svc, content)
    return {"ok": True, "results": results}


@app.post("/api/orchestrator/automation/actions/move")
async def MoveAutomationAction(req: ActionMoveRequest) -> Dict[str, Any]:
    svc = _get_services()
    content = _get_automation_content(svc)
    actions_any = content.get("actions", [])
    actions: List[Dict[str, Any]] = list(actions_any) if isinstance(actions_any, list) else []
    uuid_str = str(req.uuid)
    idx = find_item_index(actions, uuid_str)
    if idx < 0:
        raise HTTPException(status_code=404, detail="Action uuid not found")
    dir_norm = (req.direction or "").strip().lower()
    if dir_norm == "up":
        if idx > 0:
            actions[idx - 1], actions[idx] = actions[idx], actions[idx - 1]
    elif dir_norm == "down":
        if idx < len(actions) - 1:
            actions[idx + 1], actions[idx] = actions[idx], actions[idx + 1]
    else:
        raise HTTPException(status_code=400, detail="direction must be 'up' or 'down'")
    content["actions"] = actions
    _update_automation_content(svc, content)
    await _notify_automation_change()
    results = await _push_automation_to_clusters(svc, content)
    return {"ok": True, "results": results}


@app.post("/api/orchestrator/automation/actions/run")
async def RunAutomationAction(req: ActionRunRequest) -> Dict[str, Any]:
    svc = _get_services()
    cluster_uuid = req.clusterUuid
    if cluster_uuid is None:
        raise HTTPException(status_code=400, detail="clusterUuid is required")

    content = _get_automation_content(svc)
    actions_any = content.get("actions", [])
    actions: List[Dict[str, Any]] = list(actions_any) if isinstance(actions_any, list) else []
    uuid_str = str(req.uuid)
    if find_item_index(actions, uuid_str) < 0:
        raise HTTPException(status_code=404, detail="Action uuid not found")

    sync_result = await _push_automation_to_cluster(svc, content, cluster_uuid)
    if not bool(sync_result.get("ok", False)):
        raise HTTPException(status_code=502, detail=str(sync_result.get("error", "sync failed")))

    base = _require_cluster_base_url(svc, cluster_uuid)
    return await _proxy_json("POST", base, "/api/actions/run", body={"uuid": uuid_str})


def _get_actions_list_payload(svc: OrchestratorServices) -> List[ActionItemDto]:
    content = _get_automation_content(svc)
    items: List[ActionItemDto] = []
    actions_list = cast(List[Any], content.get("actions", []))
    for item_any in actions_list:
        if not isinstance(item_any, dict):
            continue
        item: Dict[str, Any] = cast(Dict[str, Any], item_any)
        steps_any = item.get("steps", [])
        steps: List[MacroStepDto] = []
        if isinstance(steps_any, list):
            for s_any in cast(List[Any], steps_any):
                if not isinstance(s_any, dict):
                    continue
                s: Dict[str, Any] = cast(Dict[str, Any], s_any)
                action_raw = str(s.get("action", "") or "").strip()
                try:
                    action = MacroTypeDto(action_raw)
                except Exception:
                    continue
                params = s.get("parameters", {})
                if not isinstance(params, dict):
                    params = {}
                steps.append(MacroStepDto(action=action, parameters=dict(cast(Dict[str, Any], params))))
        items.append(ActionItemDto(uuid=str(item.get("uuid", "")), name=str(item.get("name", "")), steps=steps))
    return items


@app.get("/api/orchestrator/automation/actions/stream")
async def AutomationActionsStream(request: Request) -> StreamingResponse:
    svc = _get_services()

    async def event_stream():
        yield "retry: 1000\n\n"

        last_seq = -1
        last_keepalive = time.monotonic()

        while True:
            if not svc.IsRunning():
                break

            seq = svc.GetAutomationSequence()
            if seq != last_seq:
                last_seq = seq
                payload = _get_actions_list_payload(svc)
                data = json.dumps([p.model_dump() for p in payload], separators=(",", ":"))
                yield f"event: actions\ndata: {data}\n\n"

            now = time.monotonic()
            # Wait for condition or keepalive timeout
            cond = getattr(app.state, "automation_cond", None)
            if cond:
                try:
                    async with cond:
                        # Wait up to 10s for a change
                        try:
                            # print(f"[ActionsStream] Waiting on condition... seq={seq}")
                            await asyncio.wait_for(cond.wait(), timeout=10.0)
                            print("[ActionsStream] Woke up from condition!")
                        except asyncio.TimeoutError:
                            # print("[ActionsStream] Keepalive")
                            yield ": keepalive\n\n"
                            last_keepalive = time.monotonic()
                except asyncio.CancelledError:
                    break
            else:
                await asyncio.sleep(1.0)
            
            if await request.is_disconnected():
                break

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/api/orchestrator/automation/conditions")
def GetAutomationConditions() -> List[ConditionItemDto]:
    svc = _get_services()
    content = _get_automation_content(svc)
    items: List[ConditionItemDto] = []
    for item_any in content.get("conditions", []):
        if not isinstance(item_any, dict):
            continue
        item: Dict[str, Any] = cast(Dict[str, Any], item_any)
        roi_any = item.get("roi", {})
        roi_dict = cast(Dict[str, Any], roi_any) if isinstance(roi_any, dict) else {}
        roi = ConditionRoiDto(
            xNormalized=float(roi_dict.get("xNormalized", 0.0) or 0.0),
            yNormalized=float(roi_dict.get("yNormalized", 0.0) or 0.0),
            widthNormalized=float(roi_dict.get("widthNormalized", 0.0) or 0.0),
            heightNormalized=float(roi_dict.get("heightNormalized", 0.0) or 0.0),
        )
        type_raw = str(item.get("type", "") or "ImageMatchRoi")
        try:
            ctype = ConditionTypeDto(type_raw)
        except Exception:
            ctype = ConditionTypeDto.ImageMatchRoi
        items.append(ConditionItemDto(uuid=str(item.get("uuid", "")), name=str(item.get("name", "")), type=ctype, roi=roi))
    return items


@app.post("/api/orchestrator/automation/conditions")
async def AddAutomationCondition(req: ConditionUpsertRequest) -> Dict[str, Any]:
    svc = _get_services()
    name = (req.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name cannot be empty")
    if req.roi.widthNormalized <= 0 or req.roi.heightNormalized <= 0:
        raise HTTPException(status_code=400, detail="roi width/height must be > 0")

    content = _get_automation_content(svc)
    conditions_any = content.get("conditions", [])
    conditions: List[Dict[str, Any]] = list(conditions_any) if isinstance(conditions_any, list) else []
    uuid_str = str(uuid4())
    template_b64 = req.templateImageBase64
    if not template_b64 and bool(req.templateFromLive):
        if req.clusterUuid is None:
            raise HTTPException(status_code=400, detail="clusterUuid is required for templateFromLive")
        frame = await _fetch_cluster_latest_frame(svc, req.clusterUuid)
        if frame is None:
            raise HTTPException(status_code=404, detail="No captured frame available for templateFromLive. Start capture first.")
        roi = {
            "xNormalized": float(req.roi.xNormalized),
            "yNormalized": float(req.roi.yNormalized),
            "widthNormalized": float(req.roi.widthNormalized),
            "heightNormalized": float(req.roi.heightNormalized),
        }
        crop = crop_frame_normalized(frame, roi)
        template_b64 = encode_png_b64(crop)
    new_item = {
        "uuid": uuid_str,
        "name": name,
        "type": req.type.value,
        "roi": {
            "xNormalized": float(req.roi.xNormalized),
            "yNormalized": float(req.roi.yNormalized),
            "widthNormalized": float(req.roi.widthNormalized),
            "heightNormalized": float(req.roi.heightNormalized),
        },
        "templateImageBase64": template_b64,
    }
    conditions.append(new_item)
    content["conditions"] = conditions
    _update_automation_content(svc, content)
    results = await _push_automation_to_clusters(svc, content)
    return {"ok": True, "uuid": uuid_str, "results": results}


@app.post("/api/orchestrator/automation/conditions/remove_uuid")
async def RemoveAutomationCondition(req: ConditionUuidRequest) -> Dict[str, Any]:
    svc = _get_services()
    content = _get_automation_content(svc)
    conditions_any = content.get("conditions", [])
    conditions: List[Dict[str, Any]] = list(conditions_any) if isinstance(conditions_any, list) else []
    uuid_str = str(req.uuid)
    idx = find_item_index(conditions, uuid_str)
    if idx < 0:
        raise HTTPException(status_code=404, detail="Condition uuid not found")
    conditions.pop(idx)
    content["conditions"] = conditions
    _update_automation_content(svc, content)
    results = await _push_automation_to_clusters(svc, content)
    return {"ok": True, "results": results}


@app.post("/api/orchestrator/automation/conditions/move")
async def MoveAutomationCondition(req: ConditionMoveRequest) -> Dict[str, Any]:
    svc = _get_services()
    content = _get_automation_content(svc)
    conditions_any = content.get("conditions", [])
    conditions: List[Dict[str, Any]] = list(conditions_any) if isinstance(conditions_any, list) else []
    uuid_str = str(req.uuid)
    idx = find_item_index(conditions, uuid_str)
    if idx < 0:
        raise HTTPException(status_code=404, detail="Condition uuid not found")
    dir_norm = (req.direction or "").strip().lower()
    if dir_norm == "up":
        if idx > 0:
            conditions[idx - 1], conditions[idx] = conditions[idx], conditions[idx - 1]
    elif dir_norm == "down":
        if idx < len(conditions) - 1:
            conditions[idx + 1], conditions[idx] = conditions[idx], conditions[idx + 1]
    else:
        raise HTTPException(status_code=400, detail="direction must be 'up' or 'down'")
    content["conditions"] = conditions
    _update_automation_content(svc, content)
    results = await _push_automation_to_clusters(svc, content)
    return {"ok": True, "results": results}


@app.post("/api/orchestrator/automation/conditions/set_from_live")
async def SetAutomationCondition(req: ConditionSetFromLiveRequest) -> Dict[str, Any]:
    svc = _get_services()
    content = _get_automation_content(svc)
    conditions_any = content.get("conditions", [])
    conditions: List[Dict[str, Any]] = list(conditions_any) if isinstance(conditions_any, list) else []
    uuid_str = str(req.uuid)
    idx = find_item_index(conditions, uuid_str)
    if idx < 0:
        raise HTTPException(status_code=404, detail="Condition uuid not found")

    item = dict(conditions[idx])
    name = (req.name or "").strip() or str(item.get("name", ""))
    ctype = req.type.value if req.type is not None else str(item.get("type", "ImageMatchRoi"))
    item["name"] = name
    item["type"] = ctype
    item["roi"] = {
        "xNormalized": float(req.roi.xNormalized),
        "yNormalized": float(req.roi.yNormalized),
        "widthNormalized": float(req.roi.widthNormalized),
        "heightNormalized": float(req.roi.heightNormalized),
    }
    if req.templateImageBase64:
        item["templateImageBase64"] = req.templateImageBase64
    elif bool(req.templateFromLive):
        if req.clusterUuid is None:
            raise HTTPException(status_code=400, detail="clusterUuid is required for templateFromLive")
        frame = await _fetch_cluster_latest_frame(svc, req.clusterUuid)
        if frame is None:
            raise HTTPException(status_code=404, detail="No captured frame available for templateFromLive. Start capture first.")
        roi = item.get("roi", {})
        crop = crop_frame_normalized(frame, roi if isinstance(roi, dict) else {})
        template_b64 = encode_png_b64(crop)
        if template_b64:
            item["templateImageBase64"] = template_b64
    conditions[idx] = item

    content["conditions"] = conditions
    _update_automation_content(svc, content)
    results = await _push_automation_to_clusters(svc, content)
    return {"ok": True, "results": results}


async def _automation_conditions_status_payload(
    svc: OrchestratorServices,
    clusterUuid: Optional[UUID] = None,
) -> Dict[str, Any]:
    content = _get_automation_content(svc)
    order: List[str] = []
    by_uuid: Dict[str, Any] = {}

    frame = None
    if clusterUuid is not None:
        frame = await _fetch_cluster_latest_frame(svc, clusterUuid)

    items = content.get("conditions", [])
    if isinstance(items, list):
        for idx, item_any in enumerate(cast(List[Any], items)):
            if not isinstance(item_any, dict):
                continue
            item: Dict[str, Any] = cast(Dict[str, Any], item_any)
            uuid_str = str(item.get("uuid", ""))
            if not uuid_str:
                continue
            template_thumb = None
            template_raw = item.get("templateImageBase64", None)
            if template_raw:
                template_img = decode_image_b64(str(template_raw))
                template_thumb = encode_jpeg_b64(template_img)

            crop_thumb = None
            if frame is not None:
                roi_any = item.get("roi", {})
                roi_dict = cast(Dict[str, Any], roi_any) if isinstance(roi_any, dict) else {}
                crop = crop_frame_normalized(frame, roi_dict)
                crop_thumb = encode_jpeg_b64(crop)

            order.append(uuid_str)
            by_uuid[uuid_str] = {
                "uuid": uuid_str,
                "index": int(idx),
                "name": str(item.get("name", "")),
                "type": str(item.get("type", "ImageMatchRoi")),
                "templateThumbBase64": template_thumb,
                "cropThumbBase64": crop_thumb,
                "last": None,
            }
    return {"order": order, "byUuid": by_uuid}


@app.get("/api/orchestrator/automation/conditions/status")
async def GetAutomationConditionsStatus(clusterUuid: Optional[UUID] = None) -> Dict[str, Any]:
    svc = _get_services()
    return await _automation_conditions_status_payload(svc, clusterUuid=clusterUuid)


@app.get("/api/orchestrator/automation/conditions/stream")
async def AutomationConditionsStream(
    request: Request,
    clusterUuid: Optional[UUID] = None,
) -> StreamingResponse:
    svc = _get_services()

    async def event_stream():
        yield "retry: 1000\n\n"

        last_data: Optional[str] = None
        last_keepalive = time.monotonic()

        while True:
            if not svc.IsRunning():
                break

            # Now we can safely await the async function on the main loop
            try:
                payload = await _automation_conditions_status_payload(svc, clusterUuid=clusterUuid)
            except Exception:
                # If fetching fails (e.g. cluster offline), skip this frame but keep stream alive
                payload = {"order": [], "byUuid": {}}

            data = json.dumps(payload, separators=(",", ":"))
            if data != last_data:
                last_data = data
                yield f"event: status\ndata: {data}\n\n"

            now = time.monotonic()
            if now - last_keepalive >= 10.0:
                yield ": keepalive\n\n"
                last_keepalive = now

            # Use async sleep instead of blocking thread
            await asyncio.sleep(0.5)
            
            if await request.is_disconnected():
                break

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/api/orchestrator/automation/triggers")
def GetAutomationTriggers() -> List[TriggerItemDto]:
    svc = _get_services()
    content = _get_automation_content(svc)
    items: List[TriggerItemDto] = []
    triggers_list = cast(List[Any], content.get("triggers", []))
    for item_any in triggers_list:
        if not isinstance(item_any, dict):
            continue
        item: Dict[str, Any] = cast(Dict[str, Any], item_any)
        citerias_in = item.get("triggerCiterias", [])
        citerias: List[TriggerCiteriaDto] = []
        if isinstance(citerias_in, list):
            for c_any in cast(List[Any], citerias_in):
                if not isinstance(c_any, dict):
                    continue
                c: Dict[str, Any] = cast(Dict[str, Any], c_any)
                try:
                    citerias.append(
                        TriggerCiteriaDto(
                            conditionUuid=UUID(str(c.get("conditionUuid", ""))),
                            expectedValue=c.get("expectedValue", None),
                            comparator=TriggerComparatorDto(str(c.get("comparator", "Equals"))),
                        )
                    )
                except Exception:
                    continue
        mode_raw = str(item.get("criteriaMode", "All"))
        try:
            mode = TriggerCriteriaModeDto(mode_raw)
        except Exception:
            mode = TriggerCriteriaModeDto.All
        items.append(
            TriggerItemDto(
                uuid=str(item.get("uuid", "")),
                name=str(item.get("name", "")),
                enabled=bool(item.get("enabled", False)),
                retriggerMs=int(item.get("retriggerMs", 0) or 0),
                disableOnFire=bool(item.get("disableOnFire", False)),
                triggerCiterias=citerias,
                criteriaMode=mode,
                action=str(item.get("action", "")),
                targetClusterUuids=[UUID(str(u)) for u in item.get("targetClusterUuids", []) if u],
            )
        )
    return items


@app.post("/api/orchestrator/automation/triggers/upsert")
async def UpsertAutomationTrigger(req: TriggerUpsertRequest) -> Dict[str, Any]:
    svc = _get_services()
    name = (req.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name cannot be empty")

    content = _get_automation_content(svc)
    actions = cast(List[Dict[str, Any]], content.get("actions", []))
    conditions = cast(List[Dict[str, Any]], content.get("conditions", []))
    action_ids = {str(a.get("uuid", "")).strip() for a in actions}
    condition_ids = {str(c.get("uuid", "")).strip() for c in conditions}
    if str(req.action) not in action_ids:
        raise HTTPException(status_code=404, detail="Action uuid not found")

    citerias: List[Dict[str, Any]] = []
    for c in req.triggerCiterias or []:
        cond_uuid = str(c.conditionUuid)
        if cond_uuid not in condition_ids:
            raise HTTPException(status_code=404, detail="Condition uuid not found")
        citerias.append(
            {
                "conditionUuid": cond_uuid,
                "expectedValue": c.expectedValue,
                "comparator": c.comparator.value,
            }
        )

    uuid_str = str(req.uuid or uuid4())
    criteria_mode = str(req.criteriaMode.value) if req.criteriaMode is not None else "All"
    target_uuids = [str(u) for u in req.targetClusterUuids] if req.targetClusterUuids else []
    
    new_item = {
        "uuid": uuid_str,
        "name": name,
        "enabled": bool(req.enabled),
        "retriggerMs": int(getattr(req, "retriggerMs", 0) or 0),
        "disableOnFire": bool(req.disableOnFire),
        "triggerCiterias": citerias,
        "criteriaMode": criteria_mode,
        "action": str(req.action),
        "targetClusterUuids": target_uuids,
    }

    triggers_any = content.get("triggers", [])
    triggers: List[Dict[str, Any]] = list(cast(List[Any], triggers_any)) if isinstance(triggers_any, list) else []
    idx = find_item_index(triggers, uuid_str)
    if idx >= 0:
        triggers[idx] = new_item
    else:
        triggers.append(new_item)
    content["triggers"] = triggers
    _update_automation_content(svc, content)
    results = await _push_automation_to_clusters(svc, content)
    return {"ok": True, "uuid": uuid_str, "results": results}


@app.post("/api/orchestrator/automation/triggers/remove_uuid")
async def RemoveAutomationTrigger(req: TriggerUuidRequest) -> Dict[str, Any]:
    svc = _get_services()
    content = _get_automation_content(svc)
    triggers_any = content.get("triggers", [])
    triggers: List[Dict[str, Any]] = list(triggers_any) if isinstance(triggers_any, list) else []
    uuid_str = str(req.uuid)
    idx = find_item_index(triggers, uuid_str)
    if idx < 0:
        raise HTTPException(status_code=404, detail="Trigger uuid not found")
    triggers.pop(idx)
    content["triggers"] = triggers
    _update_automation_content(svc, content)
    results = await _push_automation_to_clusters(svc, content)
    return {"ok": True, "results": results}


@app.post("/api/orchestrator/automation/triggers/move")
async def MoveAutomationTrigger(req: TriggerMoveRequest) -> Dict[str, Any]:
    svc = _get_services()
    content = _get_automation_content(svc)
    triggers_any = content.get("triggers", [])
    triggers: List[Dict[str, Any]] = list(triggers_any) if isinstance(triggers_any, list) else []
    uuid_str = str(req.uuid)
    idx = find_item_index(triggers, uuid_str)
    if idx < 0:
        raise HTTPException(status_code=404, detail="Trigger uuid not found")
    dir_norm = (req.direction or "").strip().lower()
    if dir_norm == "up":
        if idx > 0:
            triggers[idx - 1], triggers[idx] = triggers[idx], triggers[idx - 1]
    elif dir_norm == "down":
        if idx < len(triggers) - 1:
            triggers[idx + 1], triggers[idx] = triggers[idx], triggers[idx + 1]
    else:
        raise HTTPException(status_code=400, detail="direction must be 'up' or 'down'")
    content["triggers"] = triggers
    _update_automation_content(svc, content)
    results = await _push_automation_to_clusters(svc, content)
    return {"ok": True, "results": results}


@app.post("/api/orchestrator/automation/triggers/set_enabled")
async def SetAutomationTriggerEnabled(req: TriggerSetEnabledRequest) -> Dict[str, Any]:
    svc = _get_services()
    content = _get_automation_content(svc)
    triggers_any = content.get("triggers", [])
    triggers: List[Dict[str, Any]] = list(triggers_any) if isinstance(triggers_any, list) else []
    uuid_str = str(req.uuid)
    idx = find_item_index(triggers, uuid_str)
    if idx < 0:
        raise HTTPException(status_code=404, detail="Trigger uuid not found")
    item = dict(triggers[idx])
    item["enabled"] = bool(req.enabled)
    triggers[idx] = item
    content["triggers"] = triggers
    _update_automation_content(svc, content)
    results = await _push_automation_to_clusters(svc, content)
    return {"ok": True, "uuid": uuid_str, "enabled": bool(req.enabled), "results": results}


@app.get("/api/orchestrator/automation/triggers/status")
def GetAutomationTriggerStatus() -> Dict[str, Any]:
    svc = _get_services()
    content = _get_automation_content(svc)
    actions = cast(List[Dict[str, Any]], content.get("actions", []))
    action_name_by_uuid: Dict[str, str] = {}
    for a in actions:
        au = str(a.get("uuid", "")).strip()
        if au:
            action_name_by_uuid[au] = str(a.get("name", au))

    items: List[Dict[str, Any]] = []
    triggers = cast(List[Dict[str, Any]], content.get("triggers", []))
    for t in triggers:
        action_uuid = str(t.get("action", "")).strip()
        items.append(
            {
                    "uuid": str(t.get("uuid", "")),
                    "name": str(t.get("name", "")),
                    "enabled": bool(t.get("enabled", False)),
                    "retriggerMs": int(t.get("retriggerMs", 0) or 0),
                    "isMet": False,
                    "fireCount": 0,
                    "lastFireUnix": None,
                    "eval": [],
                    "actionUuid": action_uuid,
                    "actionName": action_name_by_uuid.get(action_uuid, action_uuid),
                    "actionIsRunning": False,
                    "actionRunCount": 0,
                    "actionLastStartedUnix": None,
                    "actionLastCompletedUnix": None,
                }
            )
    return {"items": items, "lastError": None, "macro": {}}

# -----------------------------------------------------------------------------
# Screens (layouts + assignments)
# -----------------------------------------------------------------------------



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

    seen: set[UUID] = set()
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


@app.post("/api/orchestrator/clusters/{clusterUuid}/server/reset_uuid")
async def ProxyServerResetUuid(clusterUuid: UUID) -> Dict[str, Any]:
    svc = _get_services()
    record = svc.GetCluster(clusterUuid)
    if record is None:
        raise HTTPException(status_code=404, detail="cluster not found")

    base = _require_cluster_base_url(svc, clusterUuid, allowDuplicates=True)
    payload = await _proxy_json("POST", base, "/api/server/reset_uuid")
    if not isinstance(payload, dict) or "serverUuid" not in payload:
        raise HTTPException(status_code=502, detail="cluster /api/server/reset_uuid returned invalid payload")

    try:
        new_uuid = UUID(str(payload.get("serverUuid") or "").strip())
    except Exception:
        raise HTTPException(status_code=502, detail="cluster /api/server/reset_uuid returned invalid serverUuid")

    base_url = str(record.baseUrl or "").strip()
    updated: List[ClusterRecord] = []
    if base_url:
        updated = svc.UpdateClustersServerUuidByBaseUrl(base_url, new_uuid)
    else:
        updated = [svc.UpdateClusterServerUuid(clusterUuid, new_uuid)]

    record = svc.GetCluster(new_uuid)
    if record is None and updated:
        record = updated[0]
    if record is None:
        raise HTTPException(status_code=404, detail="cluster not found")

    dup_counts = _duplicate_server_uuid_counts(svc.ListClusters(includeDecommissioned=True))
    _try_save_state(svc)
    return {
        "ok": True,
        "cluster": _to_dto(record, dup_counts.get(record.uuid, 0)).model_dump(),
        "reset": payload,
    }


# --- Actions (list) ---

@app.get("/api/orchestrator/clusters/{clusterUuid}/actions")
async def ProxyActionsList(clusterUuid: UUID) -> Any:
    svc = _get_services()
    base = _require_cluster_base_url(svc, clusterUuid)
    return await _proxy_json("GET", base, "/api/actions")


# --- Proxy body wrapper ---



# --- App window + capture ---

@app.get("/api/orchestrator/clusters/{clusterUuid}/app/defaults")
async def ProxyAppDefaults(clusterUuid: UUID) -> Any:
    svc = _get_services()
    base = _require_cluster_base_url(svc, clusterUuid)
    return await _proxy_json("GET", base, "/api/app/defaults")


@app.get("/api/orchestrator/clusters/{clusterUuid}/app/status")
async def ProxyAppStatus(clusterUuid: UUID) -> Any:
    svc = _get_services()
    base = _require_cluster_base_url(svc, clusterUuid)
    return await _proxy_json("GET", base, "/api/app/status")


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


@app.post("/api/orchestrator/clusters/{clusterUuid}/triggers/set_enabled")
async def ProxyTriggerSetEnabled(clusterUuid: UUID, req: ProxyBodyRequest) -> Any:
    svc = _get_services()
    base = _require_cluster_base_url(svc, clusterUuid)
    # The frontend sends { "uuid": "...", "enabled": true } as the body.
    # The cluster endpoint expects TriggerSetEnabledRequest which matches this structure.
    return await _proxy_json("POST", base, "/api/triggers/set_enabled", body=dict(req.body))


@app.post("/api/orchestrator/clusters/{clusterUuid}/app/close")
async def ProxyAppClose(clusterUuid: UUID) -> Any:
    svc = _get_services()
    base = _require_cluster_base_url(svc, clusterUuid)
    return await _proxy_json("POST", base, "/api/app/close")


@app.post("/api/orchestrator/clusters/{clusterUuid}/app/detach")
async def ProxyAppDetach(clusterUuid: UUID) -> Any:
    svc = _get_services()
    base = _require_cluster_base_url(svc, clusterUuid)
    return await _proxy_json("POST", base, "/api/app/detach")


@app.post("/api/orchestrator/clusters/{clusterUuid}/app/focus")
async def ProxyAppFocus(clusterUuid: UUID, req: ProxyBodyRequest) -> Any:
    svc = _get_services()
    base = _require_cluster_base_url(svc, clusterUuid)
    return await _proxy_json("POST", base, "/api/app/focus", body=dict(req.body))


@app.post("/api/orchestrator/clusters/{clusterUuid}/app/resize")
async def ProxyAppResize(clusterUuid: UUID, req: ProxyBodyRequest) -> Any:
    svc = _get_services()
    base = _require_cluster_base_url(svc, clusterUuid)
    return await _proxy_json("POST", base, "/api/app/resize", body=dict(req.body))


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


@app.post("/api/orchestrator/clusters/{clusterUuid}/control/click")
async def ProxyControlClick(clusterUuid: UUID, req: ProxyBodyRequest) -> Any:
    svc = _get_services()
    base = _require_cluster_base_url(svc, clusterUuid)
    return await _proxy_json("POST", base, "/api/control/click", body=dict(req.body))


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


@app.get("/api/orchestrator/clusters/{clusterUuid}/triggers/status/stream")
async def ProxyTriggersStatusStream(clusterUuid: UUID) -> StreamingResponse:
    svc = _get_services()
    base = _require_cluster_base_url(svc, clusterUuid)
    return await _proxy_sse(base, "/api/triggers/status/stream")


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
