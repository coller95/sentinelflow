
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
