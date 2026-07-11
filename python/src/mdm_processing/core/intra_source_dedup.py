from mdm_processing.config.models import SourceChannelConfig
from mdm_processing.core.records import IncomingRecord
from mdm_processing.core.repository import MasteryRepository


def check_intra_source_duplicate(repo: MasteryRepository, channel: SourceChannelConfig, incoming: IncomingRecord) -> None:
    if not channel.dedup_required:
        return None
    raise NotImplementedError(
        f"intra-source duplicate detection is not yet implemented (channel={channel.channel_code!r}, "
        f"dedup_strategy={channel.dedup_strategy!r}); see data_processing.md - Mastery within Source Channels"
    )
