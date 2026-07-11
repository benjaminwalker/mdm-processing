from dataclasses import dataclass
from datetime import datetime

from mdm_processing.config.models import EntityConfig, SourceChannelConfig
from mdm_processing.core.intra_source_dedup import check_intra_source_duplicate
from mdm_processing.core.matching import CrossChannelOutcome, MatchScorer, match_entity
from mdm_processing.core.records import IncomingRecord, MasterRecordRow
from mdm_processing.core.repository import MasteryRepository
from mdm_processing.core.reprocessing import WithinChannelOutcome, check_reprocessing
from mdm_processing.core.types import SourceReferenceKey


@dataclass(frozen=True)
class SubmitRecordResult:
    source_reference_key: SourceReferenceKey
    within_channel_outcome: WithinChannelOutcome
    cross_channel_outcome: CrossChannelOutcome | None
    master_key: str
    master_record: MasterRecordRow


def submit_record(
    repo: MasteryRepository,
    entity_config: EntityConfig,
    channel: SourceChannelConfig,
    incoming: IncomingRecord,
    now: datetime,
    scorer: MatchScorer | None = None,
) -> SubmitRecordResult:
    reprocessing_result = check_reprocessing(repo, incoming, now)

    if reprocessing_result.outcome == WithinChannelOutcome.NO_OP:
        master_key = repo.get_master_key_for_source(incoming.source_reference_key)
        return SubmitRecordResult(
            source_reference_key=incoming.source_reference_key,
            within_channel_outcome=reprocessing_result.outcome,
            cross_channel_outcome=None,
            master_key=master_key,
            master_record=repo.get_master_record(master_key),
        )

    check_intra_source_duplicate(repo, channel, incoming)

    match_result = match_entity(repo, entity_config, channel, incoming, now, scorer)

    return SubmitRecordResult(
        source_reference_key=incoming.source_reference_key,
        within_channel_outcome=reprocessing_result.outcome,
        cross_channel_outcome=match_result.outcome,
        master_key=match_result.master_key,
        master_record=repo.get_master_record(match_result.master_key),
    )
