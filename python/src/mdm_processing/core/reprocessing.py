from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from mdm_processing.core.checksum import compute_checksum
from mdm_processing.core.records import IncomingRecord, SourceRecord
from mdm_processing.core.repository import MasteryRepository


class WithinChannelOutcome(str, Enum):
    NO_OP = "no_op"
    NEW_VERSION = "new_version"
    NEW_RECORD = "new_record"
    # linked_intra_source_duplicate is added once intra-source dedup is built


@dataclass(frozen=True)
class ReprocessingResult:
    outcome: WithinChannelOutcome
    source_record: SourceRecord


def check_reprocessing(repo: MasteryRepository, incoming: IncomingRecord, now: datetime) -> ReprocessingResult:
    existing = repo.get_source_record(incoming.source_reference_key)
    checksum = compute_checksum(incoming.attributes)

    if existing is not None and existing.checksum == checksum:
        return ReprocessingResult(outcome=WithinChannelOutcome.NO_OP, source_record=existing)

    record = SourceRecord(
        source_reference_key=incoming.source_reference_key,
        entity_type=incoming.entity_type,
        attributes=incoming.attributes,
        checksum=checksum,
        change_timestamp=incoming.change_timestamp,
        audit_timestamp=now,
        audit_author=incoming.audit_author,
        audit_batch_id=incoming.audit_batch_id,
    )
    repo.save_source_record(record)

    outcome = WithinChannelOutcome.NEW_RECORD if existing is None else WithinChannelOutcome.NEW_VERSION
    return ReprocessingResult(outcome=outcome, source_record=record)
