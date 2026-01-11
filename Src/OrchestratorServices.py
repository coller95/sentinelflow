import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, cast
from uuid import UUID, uuid4


@dataclass(frozen=True)
class ClusterRecord:
    uuid: UUID
    serverUuid: UUID
    label: str
    baseUrl: Optional[str]
    commissionedAtUnix: float
    decommissionedAtUnix: Optional[float] = None


class OrchestratorServices:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._orchestrator_uuid: UUID = uuid4()
        self._clusters: Dict[UUID, ClusterRecord] = {}

    def GetOrchestratorUuid(self) -> UUID:
        with self._lock:
            return self._orchestrator_uuid

    def ListClusters(self, includeDecommissioned: bool = False) -> List[ClusterRecord]:
        with self._lock:
            clusters = list(self._clusters.values())
        if includeDecommissioned:
            return clusters
        return [c for c in clusters if c.decommissionedAtUnix is None]

    def GetCluster(self, clusterUuid: UUID) -> Optional[ClusterRecord]:
        with self._lock:
            return self._clusters.get(clusterUuid)

    def FindClustersByServerUuid(self, serverUuid: UUID, includeDecommissioned: bool = False) -> List[ClusterRecord]:
        with self._lock:
            matches = [c for c in self._clusters.values() if c.serverUuid == serverUuid]
        if includeDecommissioned:
            return matches
        return [c for c in matches if c.decommissionedAtUnix is None]

    def CommissionCluster(
        self,
        serverUuid: UUID,
        label: str,
        baseUrl: Optional[str],
        recordUuid: Optional[UUID] = None,
    ) -> ClusterRecord:
        clean_label = (label or "").strip()
        if not clean_label:
            raise ValueError("label is required")

        clean_base = (baseUrl or "").strip() or None
        now = float(time.time())
        record_uuid = recordUuid or serverUuid
        with self._lock:
            if record_uuid in self._clusters:
                record_uuid = uuid4()
                while record_uuid in self._clusters:
                    record_uuid = uuid4()
            record = ClusterRecord(
                uuid=record_uuid,
                serverUuid=serverUuid,
                label=clean_label,
                baseUrl=clean_base,
                commissionedAtUnix=now,
                decommissionedAtUnix=None,
            )
            self._clusters[record.uuid] = record
        return record

    def UpdateCluster(self, clusterUuid: UUID, label: Optional[str] = None, baseUrl: Optional[str] = None) -> ClusterRecord:
        with self._lock:
            existing = self._clusters.get(clusterUuid)
            if existing is None:
                raise KeyError("cluster not found")

            clean_label = (label if label is not None else existing.label)
            clean_label = (clean_label or "").strip()
            if not clean_label:
                raise ValueError("label is required")

            clean_base = (baseUrl if baseUrl is not None else existing.baseUrl)
            clean_base = (clean_base or "").strip() or None

            record = ClusterRecord(
                uuid=existing.uuid,
                serverUuid=existing.serverUuid,
                label=clean_label,
                baseUrl=clean_base,
                commissionedAtUnix=existing.commissionedAtUnix,
                decommissionedAtUnix=existing.decommissionedAtUnix,
            )
            self._clusters[clusterUuid] = record
            return record

    def DecommissionCluster(self, clusterUuid: UUID) -> ClusterRecord:
        now = float(time.time())
        with self._lock:
            existing = self._clusters.get(clusterUuid)
            if existing is None:
                raise KeyError("cluster not found")
            record = ClusterRecord(
                uuid=existing.uuid,
                serverUuid=existing.serverUuid,
                label=existing.label,
                baseUrl=existing.baseUrl,
                commissionedAtUnix=existing.commissionedAtUnix,
                decommissionedAtUnix=now,
            )
            self._clusters[clusterUuid] = record
        return record

    def RemoveCluster(self, clusterUuid: UUID) -> None:
        with self._lock:
            if clusterUuid not in self._clusters:
                raise KeyError("cluster not found")
            del self._clusters[clusterUuid]

    def ExportStateDict(self) -> Dict[str, Any]:
        with self._lock:
            orch_uuid = self._orchestrator_uuid
            clusters = list(self._clusters.values())

        return {
            "version": 1,
            "savedAtUnix": float(time.time()),
            "orchestratorUuid": str(orch_uuid),
            "clusters": [
                {
                    "uuid": str(c.uuid),
                    "serverUuid": str(c.serverUuid),
                    "label": c.label,
                    "baseUrl": c.baseUrl,
                    "commissionedAtUnix": float(c.commissionedAtUnix),
                    "decommissionedAtUnix": (None if c.decommissionedAtUnix is None else float(c.decommissionedAtUnix)),
                }
                for c in clusters
            ],
        }

    def ImportStateDict(self, obj: Dict[str, Any]) -> None:
        version = int(obj.get("version", 0) or 0)
        if version != 1:
            raise ValueError(f"Unsupported orchestrator state version: {version}")

        orch_uuid_raw = str(obj.get("orchestratorUuid", "") or "").strip()
        orch_uuid: Optional[UUID] = None
        try:
            if orch_uuid_raw:
                orch_uuid = UUID(orch_uuid_raw)
        except Exception:
            orch_uuid = None

        clusters_any: Any = obj.get("clusters", [])
        clusters: Dict[UUID, ClusterRecord] = {}
        if isinstance(clusters_any, list):
            for item_any in cast(List[Any], clusters_any):
                if not isinstance(item_any, dict):
                    continue
                item = cast(Dict[str, Any], item_any)
                cu: Optional[UUID] = None
                try:
                    cu = UUID(str(item.get("uuid", "")))
                except Exception:
                    cu = None

                label = str(item.get("label", "") or "").strip()

                server_uuid: Optional[UUID] = None
                try:
                    raw_server_uuid = str(item.get("serverUuid", "") or "").strip()
                    if raw_server_uuid:
                        server_uuid = UUID(raw_server_uuid)
                except Exception:
                    server_uuid = None
                if server_uuid is None and cu is not None:
                    server_uuid = cu
                if server_uuid is None:
                    continue
                if not label:
                    label = str(server_uuid)

                base_url_raw = str(item.get("baseUrl", "") or "").strip()
                base_url = base_url_raw or None

                commissioned_at = float(item.get("commissionedAtUnix", 0.0) or 0.0)
                decomm_raw = item.get("decommissionedAtUnix", None)
                decomm_at: Optional[float] = None
                if decomm_raw is not None:
                    try:
                        decomm_at = float(decomm_raw)
                    except Exception:
                        decomm_at = None

                record_uuid = cu or uuid4()
                while record_uuid in clusters:
                    record_uuid = uuid4()
                clusters[record_uuid] = ClusterRecord(
                    uuid=record_uuid,
                    serverUuid=server_uuid,
                    label=label,
                    baseUrl=base_url,
                    commissionedAtUnix=commissioned_at if commissioned_at > 0 else float(time.time()),
                    decommissionedAtUnix=decomm_at,
                )

        with self._lock:
            if orch_uuid is not None:
                self._orchestrator_uuid = orch_uuid
            self._clusters = clusters

    def LoadState(self, path: Union[str, Path]) -> None:
        p = Path(path)
        text = p.read_text(encoding="utf-8")
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("Invalid orchestrator state: expected object")
        self.ImportStateDict(cast(Dict[str, Any], parsed))

    def SaveState(self, path: Union[str, Path]) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = self.ExportStateDict()
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(p)
