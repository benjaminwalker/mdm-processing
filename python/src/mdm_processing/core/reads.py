from dataclasses import dataclass
from datetime import datetime

from mdm_processing.core.records import MasterRecordRow
from mdm_processing.core.repository import MasteryRepository
from mdm_processing.core.types import SourceReferenceKey


@dataclass(frozen=True)
class MasterRecordResult:
    master_record: MasterRecordRow
    resolved_from: str | None  # set only when the originally requested master_key had been superseded


def get_master_record_by_source_record(repo: MasteryRepository, key: SourceReferenceKey) -> MasterRecordResult | None:
    master_key = repo.get_master_key_for_source(key)
    if master_key is None:
        return None
    return get_master_record_by_id(repo, master_key)


def get_master_record_by_id(repo: MasteryRepository, master_key: str) -> MasterRecordResult | None:
    requested_key = master_key
    current_key = master_key
    seen: set[str] = set()

    while True:
        if current_key in seen:
            raise RuntimeError(f"redirect cycle detected while resolving master_key={requested_key!r}: {seen}")
        seen.add(current_key)

        record = repo.get_master_record(current_key)
        if record is None:
            return None

        if record.superseded_by is None:
            resolved_from = requested_key if current_key != requested_key else None
            return MasterRecordResult(master_record=record, resolved_from=resolved_from)

        current_key = record.superseded_by


def get_master_record_by_id_as_of(repo: MasteryRepository, master_key: str, as_of: datetime) -> MasterRecordResult | None:
    raise NotImplementedError(
        "point-in-time master record reconstruction is not yet implemented; master records don't persist "
        "historical attribute versions yet - see the as-of open question in docs/api_contract.md"
    )
