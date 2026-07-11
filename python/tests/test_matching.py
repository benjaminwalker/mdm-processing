from datetime import datetime, timezone

import pytest

from mdm_processing.config.models import AttributeDef, AttributeType, CandidateKeys, EntityConfig, SourceChannelConfig
from mdm_processing.core.matching import AmbiguousMatchError, CrossChannelOutcome, match_deterministic, match_probabilistic
from mdm_processing.core.records import IncomingRecord
from mdm_processing.core.types import SourceReferenceKey
from mdm_processing.storage.in_memory import InMemoryMasteryRepository

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)

ENTITY_CONFIG = EntityConfig(
    entity_type="customer",
    description="test",
    natural_keys=["ssn", "email"],
    attributes=[
        AttributeDef(name="ssn", type=AttributeType.STRING),
        AttributeDef(name="email", type=AttributeType.STRING),
        AttributeDef(name="name", type=AttributeType.STRING),
    ],
)

CHANNEL = SourceChannelConfig(
    channel_code="crm", description="test", precedence=1, dedup_required=False
)


def _incoming(source_key_value: str, attributes: dict) -> IncomingRecord:
    return IncomingRecord(
        entity_type="customer",
        source_reference_key=SourceReferenceKey(source_channel_cd="crm", source_key_name="id", source_key_value=source_key_value),
        attributes=attributes,
        change_timestamp=None,
        audit_author="ingest-job",
    )


def test_no_match_creates_new_master():
    repo = InMemoryMasteryRepository()
    incoming = _incoming("1", {"ssn": "123-45-6789", "email": "a@example.com", "name": "Alice"})

    result = match_deterministic(repo, ENTITY_CONFIG, CHANNEL, incoming, NOW)

    assert result.outcome == CrossChannelOutcome.MASTER_CREATED
    master = repo.get_master_record(result.master_key)
    assert master.attributes["ssn"].value == "123-45-6789"
    assert master.attributes["name"].value == "Alice"
    assert repo.get_master_key_for_source(incoming.source_reference_key) == result.master_key


def test_matches_existing_master_by_natural_key():
    repo = InMemoryMasteryRepository()
    first = match_deterministic(repo, ENTITY_CONFIG, CHANNEL, _incoming("1", {"ssn": "123-45-6789"}), NOW)

    second = match_deterministic(repo, ENTITY_CONFIG, CHANNEL, _incoming("2", {"ssn": "123-45-6789"}), NOW)

    assert second.outcome == CrossChannelOutcome.MASTER_MATCHED_DETERMINISTIC
    assert second.master_key == first.master_key


def test_matches_via_second_natural_key_when_first_absent():
    repo = InMemoryMasteryRepository()
    first = match_deterministic(repo, ENTITY_CONFIG, CHANNEL, _incoming("1", {"ssn": "123-45-6789", "email": "a@example.com"}), NOW)

    second = match_deterministic(repo, ENTITY_CONFIG, CHANNEL, _incoming("2", {"email": "a@example.com"}), NOW)

    assert second.outcome == CrossChannelOutcome.MASTER_MATCHED_DETERMINISTIC
    assert second.master_key == first.master_key


def test_missing_natural_key_values_are_skipped_not_matched():
    repo = InMemoryMasteryRepository()
    match_deterministic(repo, ENTITY_CONFIG, CHANNEL, _incoming("1", {"ssn": "123-45-6789"}), NOW)

    result = match_deterministic(repo, ENTITY_CONFIG, CHANNEL, _incoming("2", {"name": "no natural keys here"}), NOW)

    assert result.outcome == CrossChannelOutcome.MASTER_CREATED


def test_conflicting_natural_keys_raise_ambiguous_match():
    repo = InMemoryMasteryRepository()
    master_a = match_deterministic(repo, ENTITY_CONFIG, CHANNEL, _incoming("1", {"ssn": "111-11-1111"}), NOW)
    master_b = match_deterministic(repo, ENTITY_CONFIG, CHANNEL, _incoming("2", {"email": "b@example.com"}), NOW)
    assert master_a.master_key != master_b.master_key

    conflicting = _incoming("3", {"ssn": "111-11-1111", "email": "b@example.com"})
    with pytest.raises(AmbiguousMatchError) as exc_info:
        match_deterministic(repo, ENTITY_CONFIG, CHANNEL, conflicting, NOW)

    assert set(exc_info.value.master_keys) == {master_a.master_key, master_b.master_key}


PROBABILISTIC_ENTITY_CONFIG = EntityConfig(
    entity_type="customer",
    description="test",
    natural_keys=["ssn"],
    candidate_keys=CandidateKeys(match_strategy="fraction_match", threshold=0.8, attributes=["name", "date_of_birth"]),
    attributes=[
        AttributeDef(name="ssn", type=AttributeType.STRING),
        AttributeDef(name="name", type=AttributeType.STRING),
        AttributeDef(name="date_of_birth", type=AttributeType.STRING),
    ],
)


def _fraction_match_scorer(incoming: dict, candidate: dict) -> float:
    if not incoming:
        return 0.0
    matches = sum(1 for k, v in incoming.items() if candidate.get(k) == v)
    return matches / len(incoming)


def test_probabilistic_match_requires_candidate_keys_configured():
    repo = InMemoryMasteryRepository()
    incoming = _incoming("1", {"name": "Alice"})

    with pytest.raises(ValueError, match="no candidate_keys configured"):
        match_probabilistic(repo, ENTITY_CONFIG, CHANNEL, incoming, NOW, _fraction_match_scorer)


def test_probabilistic_match_above_threshold_matches_highest_scorer():
    repo = InMemoryMasteryRepository()
    full_match = match_deterministic(
        repo, PROBABILISTIC_ENTITY_CONFIG, CHANNEL,
        _incoming("1", {"ssn": "111-11-1111", "name": "Alice Smith", "date_of_birth": "1990-01-01"}), NOW,
    )
    match_deterministic(
        repo, PROBABILISTIC_ENTITY_CONFIG, CHANNEL,
        _incoming("2", {"ssn": "222-22-2222", "name": "Alice Smith", "date_of_birth": "1985-05-05"}), NOW,
    )

    incoming = _incoming("3", {"name": "Alice Smith", "date_of_birth": "1990-01-01"})
    result = match_probabilistic(repo, PROBABILISTIC_ENTITY_CONFIG, CHANNEL, incoming, NOW, _fraction_match_scorer)

    assert result.outcome == CrossChannelOutcome.MASTER_MATCHED_PROBABILISTIC
    assert result.master_key == full_match.master_key


def test_probabilistic_match_below_threshold_creates_new_master():
    repo = InMemoryMasteryRepository()
    match_deterministic(
        repo, PROBABILISTIC_ENTITY_CONFIG, CHANNEL,
        _incoming("1", {"ssn": "111-11-1111", "name": "Someone Else", "date_of_birth": "1970-01-01"}), NOW,
    )

    incoming = _incoming("2", {"name": "Alice Smith", "date_of_birth": "1990-01-01"})
    result = match_probabilistic(repo, PROBABILISTIC_ENTITY_CONFIG, CHANNEL, incoming, NOW, _fraction_match_scorer)

    assert result.outcome == CrossChannelOutcome.MASTER_CREATED
    assert result.master_key is not None


def test_probabilistic_match_tied_top_scores_above_threshold_raise_ambiguous():
    repo = InMemoryMasteryRepository()
    master_a = match_deterministic(
        repo, PROBABILISTIC_ENTITY_CONFIG, CHANNEL,
        _incoming("1", {"ssn": "111-11-1111", "name": "Alice Smith", "date_of_birth": "1990-01-01"}), NOW,
    )
    master_b = match_deterministic(
        repo, PROBABILISTIC_ENTITY_CONFIG, CHANNEL,
        _incoming("2", {"ssn": "222-22-2222", "name": "Alice Smith", "date_of_birth": "1990-01-01"}), NOW,
    )

    incoming = _incoming("3", {"name": "Alice Smith", "date_of_birth": "1990-01-01"})
    with pytest.raises(AmbiguousMatchError) as exc_info:
        match_probabilistic(repo, PROBABILISTIC_ENTITY_CONFIG, CHANNEL, incoming, NOW, _fraction_match_scorer)

    assert set(exc_info.value.master_keys) == {master_a.master_key, master_b.master_key}
