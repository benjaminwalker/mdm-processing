from pathlib import Path

import pytest
from pydantic import ValidationError

from mdm_processing.config.loader import (
    load_entities,
    load_entity_config,
    load_source_channel_config,
    load_source_channels,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"


def test_loads_example_entities():
    entities = load_entities(CONFIG_DIR / "entities")

    assert set(entities) == {"customer"}
    customer = entities["customer"]
    assert customer.natural_keys == ["ssn", "email", "phone"]
    assert customer.candidate_keys.match_strategy == "probabilistic_v1"
    assert customer.candidate_keys.threshold == 0.85
    address = next(a for a in customer.attributes if a.name == "address")
    assert address.ttl == "P90D"


def test_loads_example_source_channels():
    channels = load_source_channels(CONFIG_DIR / "source_channels")

    assert set(channels) == {"crm_salesforce", "legacy_import", "web_signup"}
    assert channels["crm_salesforce"].precedence == 1
    assert channels["crm_salesforce"].dedup_required is True
    assert channels["legacy_import"].dedup_required is False
    assert channels["legacy_import"].dedup_strategy is None
    assert channels["web_signup"].dedup_required is False


def test_natural_key_must_reference_known_attribute(tmp_path):
    bad_config = tmp_path / "bad.yaml"
    bad_config.write_text(
        "entity_type: broken\n"
        "description: test\n"
        "natural_keys: [ssn]\n"
        "attributes:\n"
        "  - name: email\n"
        "    type: string\n"
    )

    with pytest.raises(ValidationError, match="natural_keys reference unknown attributes"):
        load_entity_config(bad_config)


def test_invalid_ttl_format_rejected(tmp_path):
    bad_config = tmp_path / "bad.yaml"
    bad_config.write_text(
        "entity_type: broken\n"
        "description: test\n"
        "natural_keys: [email]\n"
        "attributes:\n"
        "  - name: email\n"
        "    type: string\n"
        "    ttl: 90 days\n"
    )

    with pytest.raises(ValidationError, match="ttl must be an ISO 8601 duration"):
        load_entity_config(bad_config)


def test_dedup_required_needs_strategy(tmp_path):
    bad_config = tmp_path / "bad.yaml"
    bad_config.write_text(
        "channel_code: broken\ndescription: test\nprecedence: 1\ndedup_required: true\n"
    )

    with pytest.raises(ValidationError, match="dedup_strategy is required"):
        load_source_channel_config(bad_config)
