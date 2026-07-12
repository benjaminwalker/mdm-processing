from datetime import datetime, timezone

import pytest

from mdm_processing.config.models import AttributeDef, AttributeType, EntityConfig, SourceChannelConfig
from mdm_processing.core.recompute import recompute_master_attributes
from mdm_processing.core.records import IncomingRecord
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
        AttributeDef(name="email", type=AttributeType.STRING),
    ],
)

HIGH_PRECEDENCE_CHANNEL = SourceChannelConfig(channel_code="crm", description="test", precedence=1, dedup_required=False)
LOW_PRECEDENCE_CHANNEL = SourceChannelConfig(channel_code="legacy", description="test", precedence=20, dedup_required=False)
CHANNELS = {"crm": HIGH_PRECEDENCE_CHANNEL, "legacy": LOW_PRECEDENCE_CHANNEL}


def _incoming(channel_cd: str, source_key_value: str, attributes: dict) -> IncomingRecord:
    return IncomingRecord(
        entity_type="customer",
        source_reference_key=SourceReferenceKey(source_channel_cd=channel_cd, source_key_name="id", source_key_value=source_key_value),
        attributes=attributes,
        change_timestamp=None,
        audit_author="ingest-job",
    )


def test_recompute_raises_for_unknown_master():
    repo = InMemoryMasteryRepository()

    with pytest.raises(ValueError, match="no master record found"):
        recompute_master_attributes(repo, ENTITY_CONFIG, CHANNELS, "M-missing", NOW, "recompute-job")


def test_recompute_over_single_contributor_matches_original():
    repo = InMemoryMasteryRepository()
    created = submit_record(repo, ENTITY_CONFIG, LOW_PRECEDENCE_CHANNEL, _incoming("legacy", "1", {"ssn": "123-45-6789", "name": "Alice"}), NOW)

    result = recompute_master_attributes(repo, ENTITY_CONFIG, CHANNELS, created.master_key, LATER, "recompute-job")

    assert result.attributes["name"].value == "Alice"
    assert result.metadata_audit_timestamp == LATER
    assert result.metadata_audit_author == "recompute-job"
    assert result.created_at == created.master_record.created_at


def test_recompute_pulls_in_attributes_from_a_second_contributor_not_present_at_creation():
    repo = InMemoryMasteryRepository()
    created = submit_record(repo, ENTITY_CONFIG, LOW_PRECEDENCE_CHANNEL, _incoming("legacy", "1", {"ssn": "123-45-6789", "name": "Alice"}), NOW)
    assert "email" not in created.master_record.attributes
    # a second source matches this master deterministically but submit_record doesn't merge its data in
    submit_record(repo, ENTITY_CONFIG, HIGH_PRECEDENCE_CHANNEL, _incoming("crm", "2", {"ssn": "123-45-6789", "email": "a@example.com"}), NOW)

    result = recompute_master_attributes(repo, ENTITY_CONFIG, CHANNELS, created.master_key, LATER, "recompute-job")

    assert result.attributes["email"].value == "a@example.com"
    assert result.attributes["name"].value == "Alice"


def test_recompute_applies_precedence_across_contributors():
    repo = InMemoryMasteryRepository()
    created = submit_record(repo, ENTITY_CONFIG, LOW_PRECEDENCE_CHANNEL, _incoming("legacy", "1", {"ssn": "123-45-6789", "name": "Legacy Name"}), NOW)
    submit_record(repo, ENTITY_CONFIG, HIGH_PRECEDENCE_CHANNEL, _incoming("crm", "2", {"ssn": "123-45-6789", "name": "CRM Name"}), NOW)

    result = recompute_master_attributes(repo, ENTITY_CONFIG, CHANNELS, created.master_key, LATER, "recompute-job")

    assert result.attributes["name"].value == "CRM Name"


def test_recompute_resolves_most_recent_within_channel_before_applying_cross_channel_precedence():
    repo = InMemoryMasteryRepository()
    created = submit_record(repo, ENTITY_CONFIG, LOW_PRECEDENCE_CHANNEL, _incoming("legacy", "1", {"ssn": "123-45-6789", "name": "Legacy Old"}), NOW)
    submit_record(repo, ENTITY_CONFIG, LOW_PRECEDENCE_CHANNEL, _incoming("legacy", "2", {"ssn": "123-45-6789", "name": "Legacy New"}), LATER)
    submit_record(repo, ENTITY_CONFIG, HIGH_PRECEDENCE_CHANNEL, _incoming("crm", "3", {"ssn": "123-45-6789", "name": "CRM Name"}), NOW)

    result = recompute_master_attributes(repo, ENTITY_CONFIG, CHANNELS, created.master_key, LATER, "recompute-job")

    # highest-precedence channel wins overall, even though a lower-precedence channel has more recent data
    assert result.attributes["name"].value == "CRM Name"
    assert result.attributes["name"].winning_source.source_channel_cd == "crm"


def test_recompute_most_recent_wins_among_multiple_same_channel_contributors():
    repo = InMemoryMasteryRepository()
    created = submit_record(repo, ENTITY_CONFIG, LOW_PRECEDENCE_CHANNEL, _incoming("legacy", "1", {"ssn": "123-45-6789", "name": "Legacy Old"}), NOW)
    submit_record(repo, ENTITY_CONFIG, LOW_PRECEDENCE_CHANNEL, _incoming("legacy", "2", {"ssn": "123-45-6789", "name": "Legacy New"}), LATER)

    result = recompute_master_attributes(repo, ENTITY_CONFIG, CHANNELS, created.master_key, LATER, "recompute-job")

    assert result.attributes["name"].value == "Legacy New"
    assert result.attributes["name"].winning_source.source_key_value == "2"


def test_recompute_omits_attribute_with_no_contributors():
    repo = InMemoryMasteryRepository()
    created = submit_record(repo, ENTITY_CONFIG, LOW_PRECEDENCE_CHANNEL, _incoming("legacy", "1", {"ssn": "123-45-6789"}), NOW)

    result = recompute_master_attributes(repo, ENTITY_CONFIG, CHANNELS, created.master_key, LATER, "recompute-job")

    assert "name" not in result.attributes
    assert "email" not in result.attributes
