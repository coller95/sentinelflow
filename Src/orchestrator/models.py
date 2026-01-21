from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, cast
from uuid import UUID

from pydantic import BaseModel, model_validator


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


class ClusterItemDto(BaseModel):
    uuid: str
    serverUuid: str
    label: str
    baseUrl: Optional[str]
    commissionedAtUnix: float
    decommissionedAtUnix: Optional[float] = None
    duplicateCount: int = 0
    isDuplicate: bool = False


class UpdateClusterRequest(BaseModel):
    label: Optional[str] = None
    baseUrl: Optional[str] = None


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


# -----------------------------------------------------------------------------
# Automation (global)
# -----------------------------------------------------------------------------

class MacroTypeDto(str, Enum):
    Click = "Click"
    KeyStroke = "KeyStroke"
    Delay = "Delay"


class MacroStepDto(BaseModel):
    action: MacroTypeDto
    parameters: Dict[str, Any] = {}


class ActionItemDto(BaseModel):
    uuid: str
    name: str
    steps: List[MacroStepDto]


class ActionUpsertRequest(BaseModel):
    uuid: Optional[UUID] = None
    name: str
    steps: List[MacroStepDto] = []


class ActionUuidRequest(BaseModel):
    uuid: UUID


class ActionRunRequest(BaseModel):
    uuid: UUID
    clusterUuid: Optional[UUID] = None


class ActionMoveRequest(BaseModel):
    uuid: UUID
    direction: str  # 'up' | 'down'


class TriggerComparatorDto(str, Enum):
    Equals = "Equals"
    NotEquals = "NotEquals"
    GreaterThan = "GreaterThan"
    LessThan = "LessThan"
    GreaterThanOrEqual = "GreaterThanOrEqual"
    LessThanOrEqual = "LessThanOrEqual"


class TriggerCriteriaModeDto(str, Enum):
    All = "All"
    Any = "Any"


class TriggerCiteriaDto(BaseModel):
    conditionUuid: UUID
    expectedValue: Any
    comparator: TriggerComparatorDto


class TriggerItemDto(BaseModel):
    uuid: str
    name: str
    enabled: bool = False
    retriggerMs: int = 0
    disableOnFire: bool = False
    triggerCiterias: List[TriggerCiteriaDto] = []
    criteriaMode: TriggerCriteriaModeDto = TriggerCriteriaModeDto.All
    action: str
    targetClusterUuids: List[UUID] = []


class TriggerUpsertRequest(BaseModel):
    uuid: Optional[UUID] = None
    name: str
    enabled: bool = False
    retriggerMs: int = 0
    disableOnFire: bool = False
    triggerCiterias: List[TriggerCiteriaDto] = []
    criteriaMode: Optional[TriggerCriteriaModeDto] = None
    action: UUID
    targetClusterUuids: List[UUID] = []


class TriggerUuidRequest(BaseModel):
    uuid: UUID


class TriggerMoveRequest(BaseModel):
    uuid: UUID
    direction: str  # 'up' | 'down'


class TriggerSetEnabledRequest(BaseModel):
    uuid: UUID
    enabled: bool


class AutomationStateImportRequest(BaseModel):
    state: Dict[str, Any]
    keepServerUuid: bool = True


class ConditionTypeDto(str, Enum):
    ImageMatchRoi = "ImageMatchRoi"
    ProgressBar = "ProgressBar"


class ConditionRoiDto(BaseModel):
    xNormalized: float
    yNormalized: float
    widthNormalized: float
    heightNormalized: float


class ConditionItemDto(BaseModel):
    uuid: str
    name: str
    type: ConditionTypeDto
    roi: ConditionRoiDto


class ConditionUuidRequest(BaseModel):
    uuid: UUID


class ConditionMoveRequest(BaseModel):
    uuid: UUID
    direction: str  # 'up' | 'down'


class ConditionSetFromLiveRequest(BaseModel):
    uuid: UUID
    roi: ConditionRoiDto
    name: Optional[str] = None
    type: Optional[ConditionTypeDto] = None
    templateImageBase64: Optional[str] = None
    templateFromLive: bool = True
    clusterUuid: Optional[UUID] = None


class ConditionUpsertRequest(BaseModel):
    name: str
    type: ConditionTypeDto
    roi: ConditionRoiDto
    templateImageBase64: Optional[str] = None
    templateFromLive: bool = False
    clusterUuid: Optional[UUID] = None


# -----------------------------------------------------------------------------
# Screens
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


# -----------------------------------------------------------------------------
# Orchestrator State
# -----------------------------------------------------------------------------

class OrchestratorImportRequest(BaseModel):
    state: Dict[str, Any]


# -----------------------------------------------------------------------------
# Proxy models
# -----------------------------------------------------------------------------

class ProxyBodyRequest(BaseModel):
    body: Dict[str, Any] = {}

    @model_validator(mode="before")
    @classmethod
    def _normalize_body(cls, values: Any) -> Dict[str, Any]:
        if values is None:
            return {"body": {}}
        if isinstance(values, dict):
            payload = cast(Dict[str, Any], values)
            body = payload.get("body")
            if isinstance(body, dict):
                return payload
            return {"body": payload}
        return {"body": {}}
