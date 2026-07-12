import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable

from mdm_processing.config.models import EntityConfig, SourceChannelConfig
from mdm_processing.core.records import IncomingRecord, MasterRecordRow
from mdm_processing.core.repository import MasteryRepository
from mdm_processing.core.survivorship import AttributeCandidate, resolve_survivorship

# Plain dicts of candidate-key attribute name -> value in, similarity score out. Deliberately
# decoupled from our internal types so a scorer can wrap an arbitrary external model/service.
MatchScorer = Callable[[dict[str, Any], dict[str, Any]], float]


class CrossChannelOutcome(str, Enum):
    MASTER_CREATED = "master_created"
    MASTER_MATCHED_DETERMINISTIC = "master_matched_deterministic"
    MASTER_MATCHED_PROBABILISTIC = "master_matched_probabilistic"


@dataclass(frozen=True)
class MatchResult:
    outcome: CrossChannelOutcome
    master_key: str


class AmbiguousMatchError(Exception):
    def __init__(self, entity_type: str, master_keys: list[str]):
        self.entity_type = entity_type
        self.master_keys = master_keys
        super().__init__(f"match for entity_type={entity_type!r} found conflicting master records: {sorted(master_keys)}")


def find_deterministic_match(repo: MasteryRepository, entity_config: EntityConfig, incoming: IncomingRecord) -> str | None:
    matched_master_keys: set[str] = set()
    for natural_key in entity_config.natural_keys:
        value = incoming.attributes.get(natural_key)
        if value is None:
            continue
        matched_master_keys.update(repo.find_master_by_natural_key(incoming.entity_type, natural_key, value))

    if len(matched_master_keys) > 1:
        raise AmbiguousMatchError(incoming.entity_type, sorted(matched_master_keys))

    return next(iter(matched_master_keys), None)


def find_probabilistic_match(
    repo: MasteryRepository, entity_config: EntityConfig, incoming: IncomingRecord, scorer: MatchScorer
) -> str | None:
    if entity_config.candidate_keys is None:
        raise ValueError(f"entity_type={entity_config.entity_type!r} has no candidate_keys configured")

    candidate_attrs = entity_config.candidate_keys.attributes
    incoming_values = {name: incoming.attributes[name] for name in candidate_attrs if name in incoming.attributes}

    # Naive full scan - no blocking/indexing optimization yet. Fine for now, will need
    # revisiting before this runs against a nontrivial number of master records.
    best_score = float("-inf")
    best_master_keys: list[str] = []
    for master in repo.find_live_masters_by_entity_type(incoming.entity_type):
        master_values = {name: master.attributes[name].value for name in candidate_attrs if name in master.attributes}
        score = scorer(incoming_values, master_values)
        if score > best_score:
            best_score = score
            best_master_keys = [master.master_key]
        elif score == best_score:
            best_master_keys.append(master.master_key)

    if not best_master_keys or best_score < entity_config.candidate_keys.threshold:
        return None

    if len(best_master_keys) > 1:
        raise AmbiguousMatchError(incoming.entity_type, sorted(best_master_keys))

    return best_master_keys[0]


def match_entity(
    repo: MasteryRepository,
    entity_config: EntityConfig,
    channel: SourceChannelConfig,
    incoming: IncomingRecord,
    now: datetime,
    scorer: MatchScorer | None = None,
) -> MatchResult:
    # Deterministic first; probabilistic fallback only if candidate_keys + a scorer are both present; otherwise mint a new master.
    master_key = find_deterministic_match(repo, entity_config, incoming)
    if master_key is not None:
        repo.link_crosswalk(incoming.source_reference_key, master_key)
        return MatchResult(outcome=CrossChannelOutcome.MASTER_MATCHED_DETERMINISTIC, master_key=master_key)

    if entity_config.candidate_keys is not None and scorer is not None:
        master_key = find_probabilistic_match(repo, entity_config, incoming, scorer)
        if master_key is not None:
            repo.link_crosswalk(incoming.source_reference_key, master_key)
            return MatchResult(outcome=CrossChannelOutcome.MASTER_MATCHED_PROBABILISTIC, master_key=master_key)

    master_key = _create_master_from_incoming(repo, entity_config, channel, incoming, now)
    return MatchResult(outcome=CrossChannelOutcome.MASTER_CREATED, master_key=master_key)


def _create_master_from_incoming(
    repo: MasteryRepository,
    entity_config: EntityConfig,
    channel: SourceChannelConfig,
    incoming: IncomingRecord,
    now: datetime,
) -> str:
    master_key = str(uuid.uuid4())
    observed_at = incoming.change_timestamp or now
    attributes = {}
    for attribute_def in entity_config.attributes:
        if attribute_def.name not in incoming.attributes:
            continue
        candidate = AttributeCandidate(
            value=incoming.attributes[attribute_def.name],
            source_reference_key=incoming.source_reference_key,
            channel_precedence=channel.precedence,
            observed_at=observed_at,
        )
        attributes[attribute_def.name] = resolve_survivorship(attribute_def, [candidate])

    repo.save_master_record(
        MasterRecordRow(
            master_key=master_key,
            entity_type=incoming.entity_type,
            attributes=attributes,
            created_at=now,
            metadata_audit_timestamp=now,
            metadata_audit_author=incoming.audit_author,
            metadata_audit_batch_id=incoming.audit_batch_id,
        )
    )
    repo.link_crosswalk(incoming.source_reference_key, master_key)
    return master_key
