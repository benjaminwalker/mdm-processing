from datetime import datetime, timezone

import pytest

from mdm_processing.config.models import AttributeDef, AttributeType
from mdm_processing.core.survivorship import AttributeCandidate, resolve_survivorship, resolve_within_channel
from mdm_processing.core.types import SourceReferenceKey


def _ref(channel: str) -> SourceReferenceKey:
    return SourceReferenceKey(source_channel_cd=channel, source_key_name="id", source_key_value="1")


def _at(hour: int) -> datetime:
    return datetime(2026, 1, 1, hour, tzinfo=timezone.utc)


def test_no_ttl_highest_precedence_wins_even_if_stale():
    attribute_def = AttributeDef(name="address", type=AttributeType.STRING)
    candidates = [
        AttributeCandidate(value="stale but trusted", source_reference_key=_ref("crm"), channel_precedence=1, observed_at=_at(1)),
        AttributeCandidate(value="fresh but untrusted", source_reference_key=_ref("legacy"), channel_precedence=20, observed_at=_at(10)),
    ]

    resolved = resolve_survivorship(attribute_def, candidates)

    assert resolved.value == "stale but trusted"
    assert resolved.winning_source.source_channel_cd == "crm"


def test_no_ttl_precedence_tie_breaks_on_recency():
    attribute_def = AttributeDef(name="address", type=AttributeType.STRING)
    candidates = [
        AttributeCandidate(value="older", source_reference_key=_ref("crm_a"), channel_precedence=1, observed_at=_at(1)),
        AttributeCandidate(value="newer", source_reference_key=_ref("crm_b"), channel_precedence=1, observed_at=_at(5)),
    ]

    resolved = resolve_survivorship(attribute_def, candidates)

    assert resolved.value == "newer"


def test_ttl_configured_recency_wins_even_if_low_precedence():
    attribute_def = AttributeDef(name="address", type=AttributeType.STRING, ttl="P90D")
    candidates = [
        AttributeCandidate(value="stale but trusted", source_reference_key=_ref("crm"), channel_precedence=1, observed_at=_at(1)),
        AttributeCandidate(value="fresh but untrusted", source_reference_key=_ref("legacy"), channel_precedence=20, observed_at=_at(10)),
    ]

    resolved = resolve_survivorship(attribute_def, candidates)

    assert resolved.value == "fresh but untrusted"
    assert resolved.winning_source.source_channel_cd == "legacy"


def test_ttl_configured_recency_tie_breaks_on_precedence():
    attribute_def = AttributeDef(name="address", type=AttributeType.STRING, ttl="P90D")
    candidates = [
        AttributeCandidate(value="lower precedence", source_reference_key=_ref("legacy"), channel_precedence=20, observed_at=_at(5)),
        AttributeCandidate(value="higher precedence", source_reference_key=_ref("crm"), channel_precedence=1, observed_at=_at(5)),
    ]

    resolved = resolve_survivorship(attribute_def, candidates)

    assert resolved.value == "higher precedence"


def test_no_candidates_raises():
    attribute_def = AttributeDef(name="address", type=AttributeType.STRING)

    with pytest.raises(ValueError, match="no candidates"):
        resolve_survivorship(attribute_def, [])


def test_resolve_within_channel_picks_most_recent():
    candidates = [
        AttributeCandidate(value="older", source_reference_key=_ref("crm"), channel_precedence=1, observed_at=_at(1)),
        AttributeCandidate(value="newer", source_reference_key=_ref("crm"), channel_precedence=1, observed_at=_at(5)),
    ]

    winner = resolve_within_channel(candidates)

    assert winner.value == "newer"


def test_resolve_within_channel_no_candidates_raises():
    with pytest.raises(ValueError, match="no candidates"):
        resolve_within_channel([])
