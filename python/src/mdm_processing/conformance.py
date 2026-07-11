from datetime import datetime
from pathlib import Path

import yaml

from mdm_processing.config.loader import load_entity_config, load_source_channel_config
from mdm_processing.core.records import IncomingRecord
from mdm_processing.core.submit import SubmitRecordResult, submit_record
from mdm_processing.core.types import SourceReferenceKey
from mdm_processing.storage.in_memory import InMemoryMasteryRepository


def run_fixture(fixture_path: Path, config_dir: Path) -> None:
    fixture = yaml.safe_load(fixture_path.read_text())

    entity_config = load_entity_config(config_dir / "entities" / f"{fixture['entity']}.yaml")
    channel_configs = {}
    repo = InMemoryMasteryRepository()
    now = datetime.fromisoformat(fixture["now"])

    step_results: list[SubmitRecordResult] = []
    for step in fixture["steps"]:
        submit_spec = step["submit"]
        channel_code = submit_spec["channel"]
        if channel_code not in channel_configs:
            channel_configs[channel_code] = load_source_channel_config(config_dir / "source_channels" / f"{channel_code}.yaml")
        channel = channel_configs[channel_code]

        incoming = IncomingRecord(
            entity_type=fixture["entity"],
            source_reference_key=SourceReferenceKey(
                source_channel_cd=channel_code,
                source_key_name=submit_spec["source_key_name"],
                source_key_value=submit_spec["source_key_value"],
            ),
            attributes=submit_spec["attributes"],
            change_timestamp=None,
            audit_author="fixture-runner",
        )

        result = submit_record(repo, entity_config, channel, incoming, now)
        step_results.append(result)
        _check_step(fixture_path, step["expect"], result, step_results)

    if "final_master" in fixture:
        _check_final_master(fixture_path, fixture["final_master"], step_results[-1].master_record)


def _check_step(fixture_path: Path, expect: dict, result: SubmitRecordResult, step_results: list) -> None:
    actual_within = result.within_channel_outcome.value
    assert actual_within == expect["within_channel_outcome"], (
        f"{fixture_path.name}: expected within_channel_outcome={expect['within_channel_outcome']!r}, got {actual_within!r}"
    )

    expected_cross = expect.get("cross_channel_outcome")
    actual_cross = result.cross_channel_outcome.value if result.cross_channel_outcome else None
    assert actual_cross == expected_cross, (
        f"{fixture_path.name}: expected cross_channel_outcome={expected_cross!r}, got {actual_cross!r}"
    )

    if "same_master_as_step" in expect:
        ref_index = expect["same_master_as_step"]
        assert result.master_key == step_results[ref_index].master_key, (
            f"{fixture_path.name}: expected master_key to match step {ref_index}"
        )


def _check_final_master(fixture_path: Path, expected: dict, master_record) -> None:
    for attribute_name, attribute_expect in expected["attributes"].items():
        actual_attribute = master_record.attributes[attribute_name]
        assert actual_attribute.value == attribute_expect["value"], (
            f"{fixture_path.name}: attribute {attribute_name!r} expected value={attribute_expect['value']!r}, "
            f"got {actual_attribute.value!r}"
        )

        if "winning_source" in attribute_expect:
            expected_source = attribute_expect["winning_source"]
            actual_source = actual_attribute.winning_source
            assert (
                actual_source.source_channel_cd == expected_source["source_channel_cd"]
                and actual_source.source_key_name == expected_source["source_key_name"]
                and actual_source.source_key_value == expected_source["source_key_value"]
            ), f"{fixture_path.name}: attribute {attribute_name!r} winning_source mismatch, got {actual_source}"
