from datetime import datetime, timezone

from mdm_processing.core.records import IncomingRecord
from mdm_processing.core.reprocessing import WithinChannelOutcome, check_reprocessing
from mdm_processing.core.types import SourceReferenceKey
from mdm_processing.storage.in_memory import InMemoryMasteryRepository

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
LATER = datetime(2026, 1, 2, tzinfo=timezone.utc)


def _incoming(attributes: dict) -> IncomingRecord:
    return IncomingRecord(
        entity_type="customer",
        source_reference_key=SourceReferenceKey(source_channel_cd="crm", source_key_name="id", source_key_value="1"),
        attributes=attributes,
        change_timestamp=None,
        audit_author="ingest-job",
    )


def test_first_submission_is_new_record():
    repo = InMemoryMasteryRepository()

    result = check_reprocessing(repo, _incoming({"email": "a@example.com"}), NOW)

    assert result.outcome == WithinChannelOutcome.NEW_RECORD
    assert result.source_record.attributes == {"email": "a@example.com"}
    assert repo.get_source_record(result.source_record.source_reference_key) == result.source_record


def test_resubmitting_unchanged_data_is_no_op():
    repo = InMemoryMasteryRepository()
    first = check_reprocessing(repo, _incoming({"email": "a@example.com"}), NOW)

    result = check_reprocessing(repo, _incoming({"email": "a@example.com"}), LATER)

    assert result.outcome == WithinChannelOutcome.NO_OP
    assert result.source_record == first.source_record
    assert result.source_record.audit_timestamp == NOW


def test_resubmitting_changed_data_is_new_version():
    repo = InMemoryMasteryRepository()
    check_reprocessing(repo, _incoming({"email": "old@example.com"}), NOW)

    result = check_reprocessing(repo, _incoming({"email": "new@example.com"}), LATER)

    assert result.outcome == WithinChannelOutcome.NEW_VERSION
    assert result.source_record.attributes == {"email": "new@example.com"}
    assert result.source_record.audit_timestamp == LATER
    assert repo.get_source_record(result.source_record.source_reference_key) == result.source_record
