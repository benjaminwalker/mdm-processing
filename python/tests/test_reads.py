from datetime import datetime, timezone

import pytest

from mdm_processing.core.records import MasterRecordRow
from mdm_processing.core.reads import get_master_record_by_id, get_master_record_by_id_as_of, get_master_record_by_source_record
from mdm_processing.core.survivorship import ResolvedAttribute
from mdm_processing.core.types import SourceReferenceKey
from mdm_processing.storage.in_memory import InMemoryMasteryRepository

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _ref(value: str = "1") -> SourceReferenceKey:
    return SourceReferenceKey(source_channel_cd="crm", source_key_name="id", source_key_value=value)


def _master(master_key: str, superseded_by: str | None = None) -> MasterRecordRow:
    return MasterRecordRow(
        master_key=master_key,
        entity_type="customer",
        attributes={"name": ResolvedAttribute(name="name", value="Alice", observed_at=NOW, winning_source=_ref())},
        superseded_by=superseded_by,
    )


def test_get_by_source_record_not_found_returns_none():
    repo = InMemoryMasteryRepository()

    assert get_master_record_by_source_record(repo, _ref()) is None


def test_get_by_source_record_returns_linked_master():
    repo = InMemoryMasteryRepository()
    repo.save_master_record(_master("M-1"))
    repo.link_crosswalk(_ref(), "M-1")

    result = get_master_record_by_source_record(repo, _ref())

    assert result.master_record.master_key == "M-1"
    assert result.resolved_from is None


def test_get_by_id_not_found_returns_none():
    repo = InMemoryMasteryRepository()

    assert get_master_record_by_id(repo, "M-missing") is None


def test_get_by_id_live_record_has_no_resolved_from():
    repo = InMemoryMasteryRepository()
    repo.save_master_record(_master("M-1"))

    result = get_master_record_by_id(repo, "M-1")

    assert result.master_record.master_key == "M-1"
    assert result.resolved_from is None


def test_get_by_id_transparently_resolves_one_hop():
    repo = InMemoryMasteryRepository()
    repo.save_master_record(_master("M-old", superseded_by="M-new"))
    repo.save_master_record(_master("M-new"))

    result = get_master_record_by_id(repo, "M-old")

    assert result.master_record.master_key == "M-new"
    assert result.resolved_from == "M-old"


def test_get_by_id_transparently_resolves_multi_hop_chain():
    repo = InMemoryMasteryRepository()
    repo.save_master_record(_master("M-a", superseded_by="M-b"))
    repo.save_master_record(_master("M-b", superseded_by="M-c"))
    repo.save_master_record(_master("M-c"))

    result = get_master_record_by_id(repo, "M-a")

    assert result.master_record.master_key == "M-c"
    assert result.resolved_from == "M-a"


def test_get_by_id_detects_redirect_cycle():
    repo = InMemoryMasteryRepository()
    repo.save_master_record(_master("M-a", superseded_by="M-b"))
    repo.save_master_record(_master("M-b", superseded_by="M-a"))

    with pytest.raises(RuntimeError, match="redirect cycle"):
        get_master_record_by_id(repo, "M-a")


def test_get_by_id_as_of_not_yet_implemented():
    repo = InMemoryMasteryRepository()
    repo.save_master_record(_master("M-1"))

    with pytest.raises(NotImplementedError, match="not yet implemented"):
        get_master_record_by_id_as_of(repo, "M-1", NOW)
