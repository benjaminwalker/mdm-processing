from collections import defaultdict
from datetime import datetime

from mdm_processing.config.models import EntityConfig, SourceChannelConfig
from mdm_processing.core.records import MasterRecordRow
from mdm_processing.core.repository import MasteryRepository
from mdm_processing.core.survivorship import AttributeCandidate, resolve_survivorship, resolve_within_channel


def recompute_master_attributes(
    repo: MasteryRepository,
    entity_config: EntityConfig,
    channels: dict[str, SourceChannelConfig],
    master_key: str,
    now: datetime,
    audit_author: str,
    audit_batch_id: str | None = None,
) -> MasterRecordRow:
    existing = repo.get_master_record(master_key)
    if existing is None:
        raise ValueError(f"no master record found for master_key={master_key!r}")

    source_keys = repo.find_source_keys_for_master(master_key)
    source_records = [repo.get_source_record(key) for key in source_keys]
    source_records = [record for record in source_records if record is not None]

    attributes = {}
    for attribute_def in entity_config.attributes:
        candidates_by_channel: dict[str, list[AttributeCandidate]] = defaultdict(list)
        for source_record in source_records:
            if attribute_def.name not in source_record.attributes:
                continue
            channel_cd = source_record.source_reference_key.source_channel_cd
            candidates_by_channel[channel_cd].append(
                AttributeCandidate(
                    value=source_record.attributes[attribute_def.name],
                    source_reference_key=source_record.source_reference_key,
                    channel_precedence=channels[channel_cd].precedence,
                    observed_at=source_record.change_timestamp or source_record.audit_timestamp,
                )
            )

        if not candidates_by_channel:
            continue

        channel_representatives = [resolve_within_channel(candidates) for candidates in candidates_by_channel.values()]
        attributes[attribute_def.name] = resolve_survivorship(attribute_def, channel_representatives)

    updated = MasterRecordRow(
        master_key=master_key,
        entity_type=existing.entity_type,
        attributes=attributes,
        created_at=existing.created_at,
        metadata_audit_timestamp=now,
        metadata_audit_author=audit_author,
        metadata_audit_batch_id=audit_batch_id,
        superseded_by=existing.superseded_by,
    )
    repo.save_master_record(updated)
    return updated
