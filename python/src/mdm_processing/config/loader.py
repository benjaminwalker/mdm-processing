from pathlib import Path

import yaml

from mdm_processing.config.models import EntityConfig, SourceChannelConfig


def load_entity_config(path: Path) -> EntityConfig:
    return EntityConfig.model_validate(_read_yaml(path))


def load_source_channel_config(path: Path) -> SourceChannelConfig:
    return SourceChannelConfig.model_validate(_read_yaml(path))


def load_entities(entities_dir: Path) -> dict[str, EntityConfig]:
    entities = {}
    for path in sorted(entities_dir.glob("*.yaml")):
        entity = load_entity_config(path)
        entities[entity.entity_type] = entity
    return entities


def load_source_channels(channels_dir: Path) -> dict[str, SourceChannelConfig]:
    channels = {}
    for path in sorted(channels_dir.glob("*.yaml")):
        channel = load_source_channel_config(path)
        channels[channel.channel_code] = channel
    return channels


def _read_yaml(path: Path) -> dict:
    with path.open("r") as f:
        return yaml.safe_load(f)
