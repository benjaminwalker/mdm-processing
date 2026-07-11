from datetime import datetime, timezone

import pytest

from mdm_processing.config.models import AttributeDef, AttributeType, CandidateKeys, EntityConfig, SourceChannelConfig
from mdm_processing.core.matching import CrossChannelOutcome
from mdm_processing.core.records import IncomingRecord
from mdm_processing.core.reprocessing import WithinChannelOutcome
from mdm_processing.core.submit import submit_record
from mdm_processing.core.types import SourceReferenceKey
from mdm_processing.storage.in_memory import InMemoryMasteryRepository

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
LATER = datetime(2026, 1, 2, tzinfo=timezone.utc)

ENTITY_CONFIG = EntityConfig(
    entity_type="customer",
    description="test",
    natural_keys=["ssn"],
    attributes=[
        AttributeDef(name="ssn", type=AttributeType.STRING),
        AttributeDef(name="name", type=AttributeType.STRING),
    ],
)

CHANNEL = SourceChannelConfig(channel_code="crm", description="test", precedence=1, dedup_required=False)

DEDUP_CHANNEL = SourceChannelConfig(
    channel_code="legacy", description="test", precedence=20, dedup_required=True, dedup_strategy="legacy_dedup_v1"
)


def _incoming(channel_cd: str, source_key_value: str, attributes: dict) -> IncomingRecord:
    return IncomingRecord(
        entity_type="customer",
        source_reference_key=SourceReferenceKey(source_channel_cd=channel_cd, source_key_name="id", source_key_value=source_key_value),
        attributes=attributes,
        change_timestamp=None,
        audit_author="ingest-job",
    )


def test_first_submission_creates_master():
    repo = InMemoryMasteryRepository()
    incoming = _incoming("crm", "1", {"ssn": "123-45-6789", "name": "Alice"})

    result = submit_record(repo, ENTITY_CONFIG, CHANNEL, incoming, NOW)

    assert result.within_channel_outcome == WithinChannelOutcome.NEW_RECORD
    assert result.cross_channel_outcome == CrossChannelOutcome.MASTER_CREATED
    assert result.master_record.attributes["name"].value == "Alice"


def test_resubmitting_unchanged_data_is_no_op_and_skips_matching():
    repo = InMemoryMasteryRepository()
    incoming = _incoming("crm", "1", {"ssn": "123-45-6789", "name": "Alice"})
    first = submit_record(repo, ENTITY_CONFIG, CHANNEL, incoming, NOW)

    second = submit_record(repo, ENTITY_CONFIG, CHANNEL, incoming, LATER)

    assert second.within_channel_outcome == WithinChannelOutcome.NO_OP
    assert second.cross_channel_outcome is None
    assert second.master_key == first.master_key


def test_updated_record_is_rematched_to_same_master_via_natural_key():
    repo = InMemoryMasteryRepository()
    incoming_v1 = _incoming("crm", "1", {"ssn": "123-45-6789", "name": "Alice"})
    first = submit_record(repo, ENTITY_CONFIG, CHANNEL, incoming_v1, NOW)

    incoming_v2 = _incoming("crm", "1", {"ssn": "123-45-6789", "name": "Alice Smith"})
    second = submit_record(repo, ENTITY_CONFIG, CHANNEL, incoming_v2, LATER)

    assert second.within_channel_outcome == WithinChannelOutcome.NEW_VERSION
    assert second.cross_channel_outcome == CrossChannelOutcome.MASTER_MATCHED_DETERMINISTIC
    assert second.master_key == first.master_key


def test_second_source_matches_same_master_via_shared_natural_key():
    repo = InMemoryMasteryRepository()
    first = submit_record(repo, ENTITY_CONFIG, CHANNEL, _incoming("crm", "1", {"ssn": "123-45-6789", "name": "Alice"}), NOW)

    second = submit_record(repo, ENTITY_CONFIG, CHANNEL, _incoming("legacy_no_dedup", "9", {"ssn": "123-45-6789"}), NOW)

    assert second.cross_channel_outcome == CrossChannelOutcome.MASTER_MATCHED_DETERMINISTIC
    assert second.master_key == first.master_key


def test_probabilistic_scorer_is_threaded_through_end_to_end():
    repo = InMemoryMasteryRepository()
    entity_config = EntityConfig(
        entity_type="customer",
        description="test",
        natural_keys=["ssn"],
        candidate_keys=CandidateKeys(match_strategy="fraction_match", threshold=0.8, attributes=["name"]),
        attributes=[
            AttributeDef(name="ssn", type=AttributeType.STRING),
            AttributeDef(name="name", type=AttributeType.STRING),
        ],
    )

    def scorer(incoming: dict, candidate: dict) -> float:
        return 1.0 if incoming.get("name") == candidate.get("name") else 0.0

    first = submit_record(repo, entity_config, CHANNEL, _incoming("crm", "1", {"ssn": "111-11-1111", "name": "Alice"}), NOW, scorer)

    second = submit_record(repo, entity_config, CHANNEL, _incoming("crm", "2", {"name": "Alice"}), NOW, scorer)

    assert second.cross_channel_outcome == CrossChannelOutcome.MASTER_MATCHED_PROBABILISTIC
    assert second.master_key == first.master_key


def test_dedup_required_channel_raises_before_matching():
    repo = InMemoryMasteryRepository()
    incoming = _incoming("legacy", "1", {"ssn": "123-45-6789", "name": "Alice"})

    with pytest.raises(NotImplementedError):
        submit_record(repo, ENTITY_CONFIG, DEDUP_CHANNEL, incoming, NOW)

    # the reprocessing step still commits the source record even though dedup blocks further processing
    assert repo.get_source_record(incoming.source_reference_key) is not None
    assert repo.get_master_key_for_source(incoming.source_reference_key) is None
