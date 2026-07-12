from dataclasses import dataclass
from datetime import datetime
from typing import Any

from mdm_processing.core.survivorship import ResolvedAttribute
from mdm_processing.core.types import SourceReferenceKey


@dataclass(frozen=True)
class IncomingRecord:
    entity_type: str
    source_reference_key: SourceReferenceKey
    attributes: dict[str, Any]
    change_timestamp: datetime | None
    audit_author: str
    audit_batch_id: str | None = None


@dataclass(frozen=True)
class SourceRecord:
    source_reference_key: SourceReferenceKey
    entity_type: str
    attributes: dict[str, Any]
    checksum: str
    change_timestamp: datetime | None
    audit_timestamp: datetime
    audit_author: str
    audit_batch_id: str | None = None


@dataclass(frozen=True)
class MasterRecordRow:
    master_key: str
    entity_type: str
    attributes: dict[str, ResolvedAttribute]
    created_at: datetime
    metadata_audit_timestamp: datetime
    metadata_audit_author: str
    metadata_audit_batch_id: str | None = None
    superseded_by: str | None = None
