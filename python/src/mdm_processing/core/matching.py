import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from mdm_processing.config.models import EntityConfig, SourceChannelConfig
from mdm_processing.core.records import IncomingRecord, MasterRecordRow
from mdm_processing.core.repository import MasteryRepository
from mdm_processing.core.survivorship import AttributeCandidate, resolve_survivorship


class CrossChannelOutcome(str, Enum):
    MASTER_CREATED = "master_created"
    MASTER_MATCHED_DETERMINISTIC = "master_matched_deterministic"
    # master_matched_probabilistic is added once probabilistic matching is built


@dataclass(frozen=True)
class MatchResult:
    outcome: CrossChannelOutcome
    master_key: str


class AmbiguousMatchError(Exception):
    def __init__(self, entity_type: str, master_keys: list[str]):
        self.entity_type = entity_type
        self.master_keys = master_keys
        super().__init__(f"deterministic match for entity_type={entity_type!r} found conflicting master records: {sorted(master_keys)}")


def match_deterministic(
    repo: MasteryRepository,
    entity_config: EntityConfig,
    channel: SourceChannelConfig,
    incoming: IncomingRecord,
    now: datetime,
) -> MatchResult:
    matched_master_keys: set[str] = set()
    for natural_key in entity_config.natural_keys:
        value = incoming.attributes.get(natural_key)
        if value is None:
            continue
        matched_master_keys.update(repo.find_master_by_natural_key(incoming.entity_type, natural_key, value))

    if len(matched_master_keys) > 1:
        raise AmbiguousMatchError(incoming.entity_type, sorted(matched_master_keys))

    if matched_master_keys:
        master_key = next(iter(matched_master_keys))
        repo.link_crosswalk(incoming.source_reference_key, master_key)
        return MatchResult(outcome=CrossChannelOutcome.MASTER_MATCHED_DETERMINISTIC, master_key=master_key)

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

    repo.save_master_record(MasterRecordRow(master_key=master_key, entity_type=incoming.entity_type, attributes=attributes))
    repo.link_crosswalk(incoming.source_reference_key, master_key)
    return MatchResult(outcome=CrossChannelOutcome.MASTER_CREATED, master_key=master_key)
