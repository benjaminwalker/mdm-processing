from dataclasses import dataclass
from datetime import datetime
from typing import Any

from mdm_processing.config.models import AttributeDef
from mdm_processing.core.types import SourceReferenceKey


@dataclass(frozen=True)
class AttributeCandidate:
    value: Any
    source_reference_key: SourceReferenceKey
    channel_precedence: int
    observed_at: datetime


@dataclass(frozen=True)
class ResolvedAttribute:
    name: str
    value: Any
    observed_at: datetime
    winning_source: SourceReferenceKey


def resolve_within_channel(candidates: list[AttributeCandidate]) -> AttributeCandidate:
    # All candidates here share one channel, so precedence is moot - recency is the only signal to reconcile on.
    if not candidates:
        raise ValueError("no candidates provided")
    return max(candidates, key=lambda c: c.observed_at)


def resolve_survivorship(attribute_def: AttributeDef, candidates: list[AttributeCandidate]) -> ResolvedAttribute:
    # TTL configured -> recency wins outright over precedence; otherwise precedence wins. Either way, ties break on the other criterion.
    if not candidates:
        raise ValueError(f"no candidates provided for attribute {attribute_def.name!r}")

    if attribute_def.ttl is not None:
        ordered = sorted(candidates, key=lambda c: c.channel_precedence)
        ordered = sorted(ordered, key=lambda c: c.observed_at, reverse=True)
    else:
        ordered = sorted(candidates, key=lambda c: c.observed_at, reverse=True)
        ordered = sorted(ordered, key=lambda c: c.channel_precedence)

    winner = ordered[0]
    return ResolvedAttribute(
        name=attribute_def.name,
        value=winner.value,
        observed_at=winner.observed_at,
        winning_source=winner.source_reference_key,
    )
