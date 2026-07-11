from typing import Any

from mdm_processing.core.records import MasterRecordRow, SourceRecord
from mdm_processing.core.types import SourceReferenceKey


class InMemoryMasteryRepository:
    def __init__(self) -> None:
        self._source_records: dict[SourceReferenceKey, SourceRecord] = {}
        self._crosswalk: dict[SourceReferenceKey, str] = {}
        self._master_records: dict[str, MasterRecordRow] = {}

    def get_source_record(self, key: SourceReferenceKey) -> SourceRecord | None:
        return self._source_records.get(key)

    def save_source_record(self, record: SourceRecord) -> None:
        self._source_records[record.source_reference_key] = record

    def get_master_key_for_source(self, key: SourceReferenceKey) -> str | None:
        return self._crosswalk.get(key)

    def link_crosswalk(self, key: SourceReferenceKey, master_key: str) -> None:
        self._crosswalk[key] = master_key

    def repoint_crosswalk(self, old_master_key: str, new_master_key: str) -> None:
        for key, master_key in self._crosswalk.items():
            if master_key == old_master_key:
                self._crosswalk[key] = new_master_key

    def get_master_record(self, master_key: str) -> MasterRecordRow | None:
        return self._master_records.get(master_key)

    def save_master_record(self, record: MasterRecordRow) -> None:
        self._master_records[record.master_key] = record

    def find_master_by_natural_key(self, entity_type: str, attribute_name: str, value: Any) -> list[str]:
        matches = []
        for record in self._master_records.values():
            if record.superseded_by is not None or record.entity_type != entity_type:
                continue
            attribute = record.attributes.get(attribute_name)
            if attribute is not None and attribute.value == value:
                matches.append(record.master_key)
        return matches
