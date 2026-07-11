from dataclasses import dataclass


@dataclass(frozen=True)
class SourceReferenceKey:
    source_channel_cd: str
    source_key_name: str
    source_key_value: str
