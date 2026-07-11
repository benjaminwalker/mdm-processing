from datetime import datetime, timezone

from mdm_processing.core.records import MasterRecordRow, SourceRecord
from mdm_processing.core.repository import MasteryRepository
from mdm_processing.core.survivorship import ResolvedAttribute
from mdm_processing.core.types import SourceReferenceKey
from mdm_processing.storage.in_memory import InMemoryMasteryRepository


def _ref(value: str = "1") -> SourceReferenceKey:
    return SourceReferenceKey(source_channel_cd="crm", source_key_name="id", source_key_value=value)


def test_in_memory_repository_satisfies_protocol():
    assert isinstance(InMemoryMasteryRepository(), MasteryRepository)


def test_source_record_round_trip():
    repo = InMemoryMasteryRepository()
    key = _ref()
    assert repo.get_source_record(key) is None

    record = SourceRecord(
        source_reference_key=key,
        entity_type="customer",
        attributes={"email": "a@example.com"},
        checksum="abc123",
        change_timestamp=None,
        audit_timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        audit_author="ingest-job",
    )
    repo.save_source_record(record)

    assert repo.get_source_record(key) == record


def test_source_record_save_overwrites_latest_version():
    repo = InMemoryMasteryRepository()
    key = _ref()
    v1 = SourceRecord(
        source_reference_key=key,
        entity_type="customer",
        attributes={"email": "old@example.com"},
        checksum="v1",
        change_timestamp=None,
        audit_timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        audit_author="ingest-job",
    )
    v2 = SourceRecord(
        source_reference_key=key,
        entity_type="customer",
        attributes={"email": "new@example.com"},
        checksum="v2",
        change_timestamp=None,
        audit_timestamp=datetime(2026, 1, 2, tzinfo=timezone.utc),
        audit_author="ingest-job",
    )

    repo.save_source_record(v1)
    repo.save_source_record(v2)

    assert repo.get_source_record(key).checksum == "v2"


def test_crosswalk_link_and_lookup():
    repo = InMemoryMasteryRepository()
    key = _ref()
    assert repo.get_master_key_for_source(key) is None

    repo.link_crosswalk(key, "M-1")

    assert repo.get_master_key_for_source(key) == "M-1"


def test_repoint_crosswalk_moves_all_matching_entries():
    repo = InMemoryMasteryRepository()
    key_a = _ref("a")
    key_b = _ref("b")
    key_other = _ref("other")
    repo.link_crosswalk(key_a, "M-1")
    repo.link_crosswalk(key_b, "M-1")
    repo.link_crosswalk(key_other, "M-2")

    repo.repoint_crosswalk("M-1", "M-survivor")

    assert repo.get_master_key_for_source(key_a) == "M-survivor"
    assert repo.get_master_key_for_source(key_b) == "M-survivor"
    assert repo.get_master_key_for_source(key_other) == "M-2"


def test_master_record_round_trip_including_superseded_by():
    repo = InMemoryMasteryRepository()
    assert repo.get_master_record("M-1") is None

    resolved = ResolvedAttribute(
        name="email",
        value="a@example.com",
        observed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        winning_source=_ref(),
    )
    record = MasterRecordRow(
        master_key="M-1",
        entity_type="customer",
        attributes={"email": resolved},
        superseded_by="M-survivor",
    )
    repo.save_master_record(record)

    assert repo.get_master_record("M-1") == record
