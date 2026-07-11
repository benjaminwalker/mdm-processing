import pytest

from mdm_processing.config.models import SourceChannelConfig
from mdm_processing.core.intra_source_dedup import check_intra_source_duplicate
from mdm_processing.core.records import IncomingRecord
from mdm_processing.core.types import SourceReferenceKey
from mdm_processing.storage.in_memory import InMemoryMasteryRepository

INCOMING = IncomingRecord(
    entity_type="customer",
    source_reference_key=SourceReferenceKey(source_channel_cd="crm", source_key_name="id", source_key_value="1"),
    attributes={"email": "a@example.com"},
    change_timestamp=None,
    audit_author="ingest-job",
)


def test_dedup_not_required_is_a_no_op():
    channel = SourceChannelConfig(channel_code="crm", description="test", precedence=1, dedup_required=False)

    assert check_intra_source_duplicate(InMemoryMasteryRepository(), channel, INCOMING) is None


def test_dedup_required_raises_not_implemented():
    channel = SourceChannelConfig(
        channel_code="crm", description="test", precedence=1, dedup_required=True, dedup_strategy="crm_dedup_v1"
    )

    with pytest.raises(NotImplementedError, match="not yet implemented"):
        check_intra_source_duplicate(InMemoryMasteryRepository(), channel, INCOMING)
