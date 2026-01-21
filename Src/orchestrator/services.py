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
    lastSeenUnix: Optional[float] = None
    decommissionedAtUnix: Optional[float] = None


@dataclass(frozen=True)
class ConfigBundleRecord:
    uuid: UUID
    name: str
    description: str
    tags: List[str]
    content: Dict[str, Any]
    revision: int
    createdAtUnix: float
    updatedAtUnix: float
    sourceClusterUuid: Optional[UUID] = None


@dataclass(frozen=True)
class ConfigAssignmentRecord:
    clusterUuid: UUID
    configUuid: UUID
    configRevision: int
    assignedAtUnix: float


@dataclass(frozen=True)
class DisplayScreenRecord:
    label: str
    left: int
    top: int
    width: int
    height: int


@dataclass(frozen=True)
class DisplayLayoutRecord:
    uuid: UUID
    name: str
    description: str
    screens: List[DisplayScreenRecord]
    createdAtUnix: float
    updatedAtUnix: float


@dataclass(frozen=True)
class DisplayAssignmentRecord:
    clusterUuid: UUID
    layoutUuid: UUID
    screenLabel: str
    assignedAtUnix: float


class OrchestratorServices:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._running = True
        self._shutdown_event = threading.Event()
        self._orchestrator_uuid: UUID = uuid4()
        self._clusters: Dict[UUID, ClusterRecord] = {}
        self._configBundles: Dict[UUID, ConfigBundleRecord] = {}
        self._configAssignments: Dict[UUID, ConfigAssignmentRecord] = {}
        self._automation_config_uuid: Optional[UUID] = None
        self._displayLayouts: Dict[UUID, DisplayLayoutRecord] = {}
        self._displayAssignments: Dict[UUID, DisplayAssignmentRecord] = {}
        self._automation_seq: int = 0

    def IsRunning(self) -> bool:
        return self._running

    def Shutdown(self) -> None:
        self._running = False
        self._shutdown_event.set()

    def WaitShutdown(self, timeout: float) -> bool:
        return self._shutdown_event.wait(timeout)

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
            matches = [c for c in self._clusters.values() if c.uuid == serverUuid]
        if includeDecommissioned:
            return matches
        return [c for c in matches if c.decommissionedAtUnix is None]

    def _rekey_assignments_locked(self, old_uuid: UUID, new_uuid: UUID) -> None:
        if old_uuid == new_uuid:
            return

        if old_uuid in self._configAssignments:
            existing = self._configAssignments[old_uuid]
            if new_uuid not in self._configAssignments:
                self._configAssignments[new_uuid] = ConfigAssignmentRecord(
                    clusterUuid=new_uuid,
                    configUuid=existing.configUuid,
                    configRevision=existing.configRevision,
                    assignedAtUnix=existing.assignedAtUnix,
                )
            del self._configAssignments[old_uuid]

        if old_uuid in self._displayAssignments:
            existing = self._displayAssignments[old_uuid]
            if new_uuid not in self._displayAssignments:
                self._displayAssignments[new_uuid] = DisplayAssignmentRecord(
                    clusterUuid=new_uuid,
                    layoutUuid=existing.layoutUuid,
                    screenLabel=existing.screenLabel,
                    assignedAtUnix=existing.assignedAtUnix,
                )
            del self._displayAssignments[old_uuid]

    def _rekey_cluster_locked(self, old_uuid: UUID, new_uuid: UUID) -> ClusterRecord:
        existing = self._clusters.get(old_uuid)
        if existing is None:
            raise KeyError("cluster not found")
        if old_uuid == new_uuid:
            if existing.serverUuid != old_uuid:
                existing = ClusterRecord(
                    uuid=existing.uuid,
                    serverUuid=existing.uuid,
                    label=existing.label,
                    baseUrl=existing.baseUrl,
                    commissionedAtUnix=existing.commissionedAtUnix,
                    lastSeenUnix=existing.lastSeenUnix,
                    decommissionedAtUnix=existing.decommissionedAtUnix,
                )
                self._clusters[old_uuid] = existing
            return existing

        target = self._clusters.get(new_uuid)
        if target is None:
            record = ClusterRecord(
                uuid=new_uuid,
                serverUuid=new_uuid,
                label=existing.label,
                baseUrl=existing.baseUrl,
                commissionedAtUnix=existing.commissionedAtUnix,
                lastSeenUnix=existing.lastSeenUnix,
                decommissionedAtUnix=existing.decommissionedAtUnix,
            )
        else:
            merged_label = target.label or existing.label
            merged_base = target.baseUrl or existing.baseUrl
            merged_commissioned = min(target.commissionedAtUnix, existing.commissionedAtUnix)
            merged_decommissioned = target.decommissionedAtUnix
            if merged_decommissioned is None:
                merged_decommissioned = existing.decommissionedAtUnix
            record = ClusterRecord(
                uuid=new_uuid,
                serverUuid=new_uuid,
                label=merged_label,
                baseUrl=merged_base,
                commissionedAtUnix=merged_commissioned,
                lastSeenUnix=target.lastSeenUnix or existing.lastSeenUnix,
                decommissionedAtUnix=merged_decommissioned,
            )

        self._clusters[new_uuid] = record
        del self._clusters[old_uuid]
        self._rekey_assignments_locked(old_uuid, new_uuid)
        return record

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
        record_uuid = serverUuid
        with self._lock:
            existing = self._clusters.get(record_uuid)
            if existing is not None:
                record = ClusterRecord(
                    uuid=existing.uuid,
                    serverUuid=existing.uuid,
                    label=clean_label,
                    baseUrl=clean_base,
                    commissionedAtUnix=existing.commissionedAtUnix,
                    lastSeenUnix=existing.lastSeenUnix,
                    decommissionedAtUnix=None,
                )
            else:
                record = ClusterRecord(
                    uuid=record_uuid,
                    serverUuid=record_uuid,
                    label=clean_label,
                    baseUrl=clean_base,
                    commissionedAtUnix=now,
                    lastSeenUnix=None,
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
                serverUuid=existing.uuid,
                label=clean_label,
                baseUrl=clean_base,
                commissionedAtUnix=existing.commissionedAtUnix,
                lastSeenUnix=existing.lastSeenUnix,
                decommissionedAtUnix=existing.decommissionedAtUnix,
            )
            self._clusters[clusterUuid] = record
            return record

    def UpdateClusterServerUuid(self, clusterUuid: UUID, serverUuid: UUID) -> ClusterRecord:
        with self._lock:
            return self._rekey_cluster_locked(clusterUuid, serverUuid)

    def UpdateClusterLastSeen(self, clusterUuid: UUID, timestamp: float) -> Optional[ClusterRecord]:
        with self._lock:
            existing = self._clusters.get(clusterUuid)
            if existing is None:
                return None
            record = ClusterRecord(
                uuid=existing.uuid,
                serverUuid=existing.serverUuid,
                label=existing.label,
                baseUrl=existing.baseUrl,
                commissionedAtUnix=existing.commissionedAtUnix,
                lastSeenUnix=timestamp,
                decommissionedAtUnix=existing.decommissionedAtUnix,
            )
            self._clusters[clusterUuid] = record
            return record

    def UpdateClustersServerUuidByBaseUrl(self, baseUrl: str, serverUuid: UUID) -> List[ClusterRecord]:
        clean_base = (baseUrl or "").strip()
        if not clean_base:
            return []
        updated: List[ClusterRecord] = []
        with self._lock:
            matches = [c.uuid for c in self._clusters.values() if str(c.baseUrl or "").strip() == clean_base]
            for cu in matches:
                try:
                    record = self._rekey_cluster_locked(cu, serverUuid)
                except KeyError:
                    continue
                updated.append(record)
        return updated

    def DecommissionCluster(self, clusterUuid: UUID) -> ClusterRecord:
        now = float(time.time())
        with self._lock:
            existing = self._clusters.get(clusterUuid)
            if existing is None:
                raise KeyError("cluster not found")
            record = ClusterRecord(
                uuid=existing.uuid,
                serverUuid=existing.uuid,
                label=existing.label,
                baseUrl=existing.baseUrl,
                commissionedAtUnix=existing.commissionedAtUnix,
                lastSeenUnix=existing.lastSeenUnix,
                decommissionedAtUnix=now,
            )
            self._clusters[clusterUuid] = record
        return record

    def RemoveCluster(self, clusterUuid: UUID) -> None:
        with self._lock:
            if clusterUuid not in self._clusters:
                raise KeyError("cluster not found")
            del self._clusters[clusterUuid]

    def _normalize_tags(self, tags: Optional[List[str]]) -> List[str]:
        clean: List[str] = []
        seen: set[str] = set()
        for t in (tags or []):
            label = str(t or "").strip()
            if not label or label in seen:
                continue
            clean.append(label)
            seen.add(label)
        return clean

    def _normalize_config_content(self, content: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not isinstance(content, dict):
            content = {}

        app = content.get("app", {})
        if not isinstance(app, dict):
            app = {}

        seeded = bool(content.get("seeded", False))

        def _list(key: str) -> List[Any]:
            raw = content.get(key, [])
            if isinstance(raw, list):
                val: List[Any] = list(cast(List[Any], raw))
                return val
            return []

        return {
            "version": 1,
            "seeded": seeded,
            "app": dict(cast(Dict[str, Any], app)),
            "actions": _list("actions"),
            "conditions": _list("conditions"),
            "triggers": _list("triggers"),
        }

    def GetAutomationConfigUuid(self) -> Optional[UUID]:
        with self._lock:
            return self._automation_config_uuid

    def GetAutomationConfig(self) -> Optional[ConfigBundleRecord]:
        with self._lock:
            if self._automation_config_uuid is None:
                return None
            return self._configBundles.get(self._automation_config_uuid)

    def GetAutomationSequence(self) -> int:
        with self._lock:
            return self._automation_seq

    def EnsureAutomationConfig(self) -> ConfigBundleRecord:
        existing = self.GetAutomationConfig()
        if existing is not None:
            return existing

        record = self.CreateConfigBundle(
            name="Automation",
            description="Managed by orchestrator",
            tags=["automation", "global"],
            content={"version": 1, "actions": [], "conditions": [], "triggers": []},
        )
        with self._lock:
            self._automation_config_uuid = record.uuid
        return record

    def ListConfigBundles(self) -> List[ConfigBundleRecord]:
        with self._lock:
            return list(self._configBundles.values())

    def GetConfigBundle(self, configUuid: UUID) -> Optional[ConfigBundleRecord]:
        with self._lock:
            return self._configBundles.get(configUuid)

    def CreateConfigBundle(
        self,
        name: str,
        description: Optional[str],
        tags: Optional[List[str]],
        content: Optional[Dict[str, Any]],
        sourceClusterUuid: Optional[UUID] = None,
    ) -> ConfigBundleRecord:
        clean_name = (name or "").strip()
        if not clean_name:
            raise ValueError("name is required")

        clean_desc = str(description or "").strip()
        clean_tags = self._normalize_tags(tags)
        normalized_content = self._normalize_config_content(content)
        now = float(time.time())
        record_uuid = uuid4()
        with self._lock:
            while record_uuid in self._configBundles:
                record_uuid = uuid4()
            record = ConfigBundleRecord(
                uuid=record_uuid,
                name=clean_name,
                description=clean_desc,
                tags=clean_tags,
                content=normalized_content,
                revision=1,
                createdAtUnix=now,
                updatedAtUnix=now,
                sourceClusterUuid=sourceClusterUuid,
            )
            self._configBundles[record.uuid] = record
        return record

    def UpdateConfigBundle(
        self,
        configUuid: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        content: Optional[Dict[str, Any]] = None,
    ) -> ConfigBundleRecord:
        with self._lock:
            existing = self._configBundles.get(configUuid)
            if existing is None:
                raise KeyError("config bundle not found")

            clean_name = existing.name
            if name is not None:
                clean_name = (name or "").strip()
                if not clean_name:
                    raise ValueError("name is required")

            clean_desc = existing.description
            if description is not None:
                clean_desc = str(description or "").strip()

            clean_tags = existing.tags
            if tags is not None:
                clean_tags = self._normalize_tags(tags)

            new_content = existing.content
            new_revision = existing.revision
            if content is not None:
                new_content = self._normalize_config_content(content)
                new_revision = max(1, int(existing.revision) + 1)

            now = float(time.time())
            record = ConfigBundleRecord(
                uuid=existing.uuid,
                name=clean_name,
                description=clean_desc,
                tags=clean_tags,
                content=new_content,
                revision=new_revision,
                createdAtUnix=existing.createdAtUnix,
                updatedAtUnix=now,
                sourceClusterUuid=existing.sourceClusterUuid,
            )
            self._configBundles[configUuid] = record
            
            if self._automation_config_uuid == configUuid:
                self._automation_seq += 1
        return record

    def RemoveConfigBundle(self, configUuid: UUID) -> None:
        with self._lock:
            if configUuid not in self._configBundles:
                raise KeyError("config bundle not found")
            del self._configBundles[configUuid]
            self._configAssignments = {
                k: v for k, v in self._configAssignments.items() if v.configUuid != configUuid
            }

    def AssignConfigBundle(self, clusterUuid: UUID, configUuid: UUID) -> ConfigAssignmentRecord:
        now = float(time.time())
        with self._lock:
            config = self._configBundles.get(configUuid)
            if config is None:
                raise KeyError("config bundle not found")
            record = ConfigAssignmentRecord(
                clusterUuid=clusterUuid,
                configUuid=configUuid,
                configRevision=int(config.revision),
                assignedAtUnix=now,
            )
            self._configAssignments[clusterUuid] = record
        return record

    def RemoveConfigAssignment(self, clusterUuid: UUID) -> None:
        with self._lock:
            if clusterUuid not in self._configAssignments:
                raise KeyError("config assignment not found")
            del self._configAssignments[clusterUuid]

    def ListConfigAssignments(self) -> List[ConfigAssignmentRecord]:
        with self._lock:
            return list(self._configAssignments.values())

    def _normalize_screens(self, screens: Optional[List[Dict[str, Any]]]) -> List[DisplayScreenRecord]:
        out: List[DisplayScreenRecord] = []
        seen: set[str] = set()

        for s_any in (screens or []):
            label = str(s_any.get("label", "") or "").strip()
            if not label or label in seen:
                continue

            try:
                left = int(s_any.get("left", 0) or 0)
                top = int(s_any.get("top", 0) or 0)
                width = int(s_any.get("width", 0) or 0)
                height = int(s_any.get("height", 0) or 0)
            except Exception:
                continue

            if width <= 0 or height <= 0:
                continue

            out.append(DisplayScreenRecord(label=label, left=left, top=top, width=width, height=height))
            seen.add(label)

        return out

    def ListDisplayLayouts(self) -> List[DisplayLayoutRecord]:
        with self._lock:
            return list(self._displayLayouts.values())

    def GetDisplayLayout(self, layoutUuid: UUID) -> Optional[DisplayLayoutRecord]:
        with self._lock:
            return self._displayLayouts.get(layoutUuid)

    def CreateDisplayLayout(
        self,
        name: str,
        description: Optional[str],
        screens: Optional[List[Dict[str, Any]]],
    ) -> DisplayLayoutRecord:
        clean_name = (name or "").strip()
        if not clean_name:
            raise ValueError("name is required")

        clean_desc = str(description or "").strip()
        clean_screens = self._normalize_screens(screens)
        now = float(time.time())
        record_uuid = uuid4()
        with self._lock:
            while record_uuid in self._displayLayouts:
                record_uuid = uuid4()
            record = DisplayLayoutRecord(
                uuid=record_uuid,
                name=clean_name,
                description=clean_desc,
                screens=clean_screens,
                createdAtUnix=now,
                updatedAtUnix=now,
            )
            self._displayLayouts[record.uuid] = record
        return record

    def UpdateDisplayLayout(
        self,
        layoutUuid: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        screens: Optional[List[Dict[str, Any]]] = None,
    ) -> DisplayLayoutRecord:
        with self._lock:
            existing = self._displayLayouts.get(layoutUuid)
            if existing is None:
                raise KeyError("layout not found")

            clean_name = existing.name
            if name is not None:
                clean_name = (name or "").strip()
                if not clean_name:
                    raise ValueError("name is required")

            clean_desc = existing.description
            if description is not None:
                clean_desc = str(description or "").strip()

            clean_screens = existing.screens
            if screens is not None:
                clean_screens = self._normalize_screens(screens)

            now = float(time.time())
            record = DisplayLayoutRecord(
                uuid=existing.uuid,
                name=clean_name,
                description=clean_desc,
                screens=clean_screens,
                createdAtUnix=existing.createdAtUnix,
                updatedAtUnix=now,
            )
            self._displayLayouts[layoutUuid] = record

            if screens is not None:
                valid_labels = {s.label for s in clean_screens}
                self._displayAssignments = {
                    k: v
                    for k, v in self._displayAssignments.items()
                    if v.layoutUuid != layoutUuid or v.screenLabel in valid_labels
                }

        return record

    def RemoveDisplayLayout(self, layoutUuid: UUID) -> None:
        with self._lock:
            if layoutUuid not in self._displayLayouts:
                raise KeyError("layout not found")
            del self._displayLayouts[layoutUuid]
            self._displayAssignments = {
                k: v for k, v in self._displayAssignments.items() if v.layoutUuid != layoutUuid
            }

    def AssignDisplay(self, clusterUuid: UUID, layoutUuid: UUID, screenLabel: str) -> DisplayAssignmentRecord:
        clean_label = (screenLabel or "").strip()
        if not clean_label:
            raise ValueError("screenLabel is required")

        now = float(time.time())
        with self._lock:
            layout = self._displayLayouts.get(layoutUuid)
            if layout is None:
                raise KeyError("layout not found")
            labels = {s.label for s in layout.screens}
            if clean_label not in labels:
                raise ValueError("screenLabel not found in layout")

            record = DisplayAssignmentRecord(
                clusterUuid=clusterUuid,
                layoutUuid=layoutUuid,
                screenLabel=clean_label,
                assignedAtUnix=now,
            )
            self._displayAssignments[clusterUuid] = record
        return record

    def RemoveDisplayAssignment(self, clusterUuid: UUID) -> None:
        with self._lock:
            if clusterUuid not in self._displayAssignments:
                raise KeyError("assignment not found")
            del self._displayAssignments[clusterUuid]

    def ListDisplayAssignments(self) -> List[DisplayAssignmentRecord]:
        with self._lock:
            return list(self._displayAssignments.values())

    def ExportStateDict(self) -> Dict[str, Any]:
        with self._lock:
            orch_uuid = self._orchestrator_uuid
            clusters = list(self._clusters.values())
            config_bundles = list(self._configBundles.values())
            config_assignments = list(self._configAssignments.values())
            automation_uuid = self._automation_config_uuid
            display_layouts = list(self._displayLayouts.values())
            display_assignments = list(self._displayAssignments.values())

        return {
            "version": 4,
            "savedAtUnix": float(time.time()),
            "orchestratorUuid": str(orch_uuid),
            "automationConfigUuid": (None if automation_uuid is None else str(automation_uuid)),
            "clusters": [
                {
                    "uuid": str(c.uuid),
                    "serverUuid": str(c.uuid),
                    "label": c.label,
                    "baseUrl": c.baseUrl,
                    "commissionedAtUnix": float(c.commissionedAtUnix),
                    "lastSeenUnix": (None if c.lastSeenUnix is None else float(c.lastSeenUnix)),
                    "decommissionedAtUnix": (None if c.decommissionedAtUnix is None else float(c.decommissionedAtUnix)),
                }
                for c in clusters
            ],
            "configBundles": [
                {
                    "uuid": str(b.uuid),
                    "name": b.name,
                    "description": b.description,
                    "tags": list(b.tags),
                    "content": dict(b.content),
                    "revision": int(b.revision),
                    "createdAtUnix": float(b.createdAtUnix),
                    "updatedAtUnix": float(b.updatedAtUnix),
                    "sourceClusterUuid": (None if b.sourceClusterUuid is None else str(b.sourceClusterUuid)),
                }
                for b in config_bundles
            ],
            "configAssignments": [
                {
                    "clusterUuid": str(a.clusterUuid),
                    "configUuid": str(a.configUuid),
                    "configRevision": int(a.configRevision),
                    "assignedAtUnix": float(a.assignedAtUnix),
                }
                for a in config_assignments
            ],
            "displayLayouts": [
                {
                    "uuid": str(l.uuid),
                    "name": l.name,
                    "description": l.description,
                    "screens": [
                        {
                            "label": s.label,
                            "left": int(s.left),
                            "top": int(s.top),
                            "width": int(s.width),
                            "height": int(s.height),
                        }
                        for s in l.screens
                    ],
                    "createdAtUnix": float(l.createdAtUnix),
                    "updatedAtUnix": float(l.updatedAtUnix),
                }
                for l in display_layouts
            ],
            "displayAssignments": [
                {
                    "clusterUuid": str(a.clusterUuid),
                    "layoutUuid": str(a.layoutUuid),
                    "screenLabel": a.screenLabel,
                    "assignedAtUnix": float(a.assignedAtUnix),
                }
                for a in display_assignments
            ],
        }

    def ImportStateDict(self, obj: Dict[str, Any]) -> None:
        version = int(obj.get("version", 0) or 0)
        if version not in (1, 2, 3, 4):
            raise ValueError(f"Unsupported orchestrator state version: {version}")

        orch_uuid_raw = str(obj.get("orchestratorUuid", "") or "").strip()
        orch_uuid: Optional[UUID] = None
        try:
            if orch_uuid_raw:
                orch_uuid = UUID(orch_uuid_raw)
        except Exception:
            orch_uuid = None

        automation_uuid_raw = str(obj.get("automationConfigUuid", "") or "").strip()
        automation_uuid: Optional[UUID] = None
        try:
            if automation_uuid_raw:
                automation_uuid = UUID(automation_uuid_raw)
        except Exception:
            automation_uuid = None

        clusters_any: Any = obj.get("clusters", [])
        clusters: Dict[UUID, ClusterRecord] = {}
        cluster_uuid_map: Dict[UUID, UUID] = {}
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
                if server_uuid is None and cu is None:
                    continue
                record_uuid = server_uuid or cu or uuid4()
                if not label:
                    label = str(record_uuid)

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

                if record_uuid in clusters:
                    if cu is not None:
                        cluster_uuid_map[cu] = record_uuid
                    if server_uuid is not None:
                        cluster_uuid_map[server_uuid] = record_uuid
                    continue

                clusters[record_uuid] = ClusterRecord(
                    uuid=record_uuid,
                    serverUuid=record_uuid,
                    label=label,
                    baseUrl=base_url,
                    commissionedAtUnix=commissioned_at if commissioned_at > 0 else float(time.time()),
                    lastSeenUnix=float(item.get("lastSeenUnix", 0)) if item.get("lastSeenUnix") else None,
                    decommissionedAtUnix=decomm_at,
                )
                if cu is not None:
                    cluster_uuid_map[cu] = record_uuid
                if server_uuid is not None:
                    cluster_uuid_map[server_uuid] = record_uuid

        bundles_any: Any = obj.get("configBundles", [])
        bundles: Dict[UUID, ConfigBundleRecord] = {}
        if isinstance(bundles_any, list):
            for item_any in cast(List[Any], bundles_any):
                if not isinstance(item_any, dict):
                    continue
                item = cast(Dict[str, Any], item_any)
                bu: Optional[UUID] = None
                try:
                    bu = UUID(str(item.get("uuid", "")))
                except Exception:
                    bu = None

                name = str(item.get("name", "") or "").strip()
                if not name:
                    continue

                description = str(item.get("description", "") or "").strip()
                tags_any = item.get("tags", [])
                tags_list: List[str] = []
                if isinstance(tags_any, list):
                    tags_list = self._normalize_tags(cast(List[str], tags_any))

                content_any = item.get("content", None)
                if content_any is None:
                    content_any = item.get("config", None)
                if content_any is None:
                    content_any = item.get("state", None)
                content = self._normalize_config_content(cast(Optional[Dict[str, Any]], content_any))

                revision_raw = item.get("revision", 1)
                try:
                    revision = int(revision_raw)
                except Exception:
                    revision = 1
                revision = max(1, revision)

                created_raw = item.get("createdAtUnix", 0.0)
                updated_raw = item.get("updatedAtUnix", 0.0)
                try:
                    created_at = float(created_raw)
                except Exception:
                    created_at = 0.0
                try:
                    updated_at = float(updated_raw)
                except Exception:
                    updated_at = 0.0
                if created_at <= 0:
                    created_at = float(time.time())
                if updated_at <= 0:
                    updated_at = created_at

                source_uuid: Optional[UUID] = None
                try:
                    raw_source = str(item.get("sourceClusterUuid", "") or "").strip()
                    if raw_source:
                        source_uuid = UUID(raw_source)
                except Exception:
                    source_uuid = None
                if source_uuid is not None and source_uuid in cluster_uuid_map:
                    source_uuid = cluster_uuid_map[source_uuid]
                if source_uuid is not None and source_uuid not in clusters:
                    source_uuid = None

                record_uuid = bu or uuid4()
                while record_uuid in bundles:
                    record_uuid = uuid4()
                bundles[record_uuid] = ConfigBundleRecord(
                    uuid=record_uuid,
                    name=name,
                    description=description,
                    tags=tags_list,
                    content=content,
                    revision=revision,
                    createdAtUnix=created_at,
                    updatedAtUnix=updated_at,
                    sourceClusterUuid=source_uuid,
                )

        assignments_any: Any = obj.get("configAssignments", [])
        assignments: Dict[UUID, ConfigAssignmentRecord] = {}
        if isinstance(assignments_any, list):
            for item_any in cast(List[Any], assignments_any):
                if not isinstance(item_any, dict):
                    continue
                item = cast(Dict[str, Any], item_any)
                cu: Optional[UUID] = None
                try:
                    cu = UUID(str(item.get("clusterUuid", "")))
                except Exception:
                    cu = None
                if cu is not None and cu in cluster_uuid_map:
                    cu = cluster_uuid_map[cu]
                if cu is None or cu not in clusters:
                    continue

                bu: Optional[UUID] = None
                try:
                    bu = UUID(str(item.get("configUuid", "")))
                except Exception:
                    bu = None
                if bu is None or bu not in bundles:
                    continue

                revision_raw = item.get("configRevision", bundles[bu].revision)
                try:
                    revision = int(revision_raw)
                except Exception:
                    revision = int(bundles[bu].revision)

                assigned_raw = item.get("assignedAtUnix", 0.0)
                try:
                    assigned_at = float(assigned_raw)
                except Exception:
                    assigned_at = 0.0
                if assigned_at <= 0:
                    assigned_at = float(time.time())

                assignments[cu] = ConfigAssignmentRecord(
                    clusterUuid=cu,
                    configUuid=bu,
                    configRevision=revision,
                    assignedAtUnix=assigned_at,
                )

        layouts_any: Any = obj.get("displayLayouts", [])
        layouts: Dict[UUID, DisplayLayoutRecord] = {}
        if isinstance(layouts_any, list):
            for item_any in cast(List[Any], layouts_any):
                if not isinstance(item_any, dict):
                    continue
                item = cast(Dict[str, Any], item_any)
                lu: Optional[UUID] = None
                try:
                    lu = UUID(str(item.get("uuid", "")))
                except Exception:
                    lu = None

                name = str(item.get("name", "") or "").strip()
                if not name:
                    continue

                description = str(item.get("description", "") or "").strip()
                screens_any = item.get("screens", [])
                screens: List[DisplayScreenRecord] = []
                if isinstance(screens_any, list):
                    screens = self._normalize_screens(cast(List[Dict[str, Any]], screens_any))

                created_raw = item.get("createdAtUnix", 0.0)
                updated_raw = item.get("updatedAtUnix", 0.0)
                try:
                    created_at = float(created_raw)
                except Exception:
                    created_at = 0.0
                try:
                    updated_at = float(updated_raw)
                except Exception:
                    updated_at = 0.0
                if created_at <= 0:
                    created_at = float(time.time())
                if updated_at <= 0:
                    updated_at = created_at

                record_uuid = lu or uuid4()
                while record_uuid in layouts:
                    record_uuid = uuid4()
                layouts[record_uuid] = DisplayLayoutRecord(
                    uuid=record_uuid,
                    name=name,
                    description=description,
                    screens=screens,
                    createdAtUnix=created_at,
                    updatedAtUnix=updated_at,
                )

        display_assignments_any: Any = obj.get("displayAssignments", [])
        display_assignments: Dict[UUID, DisplayAssignmentRecord] = {}
        if isinstance(display_assignments_any, list):
            for item_any in cast(List[Any], display_assignments_any):
                if not isinstance(item_any, dict):
                    continue
                item = cast(Dict[str, Any], item_any)

                cu: Optional[UUID] = None
                try:
                    cu = UUID(str(item.get("clusterUuid", "")))
                except Exception:
                    cu = None
                if cu is not None and cu in cluster_uuid_map:
                    cu = cluster_uuid_map[cu]
                if cu is None or cu not in clusters:
                    continue

                lu: Optional[UUID] = None
                try:
                    lu = UUID(str(item.get("layoutUuid", "")))
                except Exception:
                    lu = None
                if lu is None or lu not in layouts:
                    continue

                screen_label = str(item.get("screenLabel", "") or "").strip()
                if not screen_label:
                    continue

                valid_labels = {s.label for s in layouts[lu].screens}
                if screen_label not in valid_labels:
                    continue

                assigned_raw = item.get("assignedAtUnix", 0.0)
                try:
                    assigned_at = float(assigned_raw)
                except Exception:
                    assigned_at = 0.0
                if assigned_at <= 0:
                    assigned_at = float(time.time())

                display_assignments[cu] = DisplayAssignmentRecord(
                    clusterUuid=cu,
                    layoutUuid=lu,
                    screenLabel=screen_label,
                    assignedAtUnix=assigned_at,
                )

        if automation_uuid is not None and automation_uuid not in bundles:
            automation_uuid = None

        with self._lock:
            if orch_uuid is not None:
                self._orchestrator_uuid = orch_uuid
            self._clusters = clusters
            self._configBundles = bundles
            self._configAssignments = assignments
            self._automation_config_uuid = automation_uuid
            self._displayLayouts = layouts
            self._displayAssignments = display_assignments

    def LoadState(self, path: Union[str, Path]) -> None:
        p = Path(path)
        text = p.read_text(encoding="utf-8")
        parsed = json.loads(text)
        self.ImportStateDict(cast(Dict[str, Any], parsed))

    def SaveState(self, path: Union[str, Path]) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = self.ExportStateDict()
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(p)
