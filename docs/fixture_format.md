# Conformance Fixture Format

YAML files under `fixtures/<entity_type>/`, one scenario per file. Each fixture drives a sequence of `Submit Record` calls against a fresh repository and asserts the resulting outcomes - this is the language-agnostic conformance suite described in `project_purpose.md`: any implementation, in any language, should produce the same outcomes for the same fixture.

Only scenarios covered by *currently implemented* behavior belong here. A fixture describing aspirational behavior (e.g. attribute merging on an already-matched master, or intra-source dedup) is not a conformance fixture, it's a spec for unbuilt behavior - keep those in `data_processing.md`'s open questions instead until they're real.

`master_key` values are runtime-generated (UUIDs) and can't be asserted directly - fixtures instead assert *relationships* (`same_master_as_step`) and specific resulting attribute values.

## Shape

```yaml
name: two_channels_share_natural_key
description: Two source channels submitting the same natural key value resolve to one master.

entity: customer          # references config/entities/<entity>.yaml
now: "2026-01-01T00:00:00Z"

steps:
  - submit:
      channel: legacy_import        # references config/source_channels/<channel>.yaml
      source_key_name: id
      source_key_value: "1"
      attributes:
        ssn: "123-45-6789"
        name: Alice Smith
    expect:
      within_channel_outcome: new_record       # no_op | new_version | new_record
      cross_channel_outcome: master_created    # master_created | master_matched_deterministic | master_matched_probabilistic | null

  - submit:
      channel: web_signup
      source_key_name: id
      source_key_value: "1"
      attributes:
        ssn: "123-45-6789"
    expect:
      within_channel_outcome: new_record
      cross_channel_outcome: master_matched_deterministic
      same_master_as_step: 0    # 0-indexed reference to an earlier step

final_master:                   # optional - checked against the last step's resulting master record
  attributes:
    name:
      value: Alice Smith
      winning_source:                # optional - which source contributed the winning value
        source_channel_cd: legacy_import
        source_key_name: id
        source_key_value: "1"
```

Notes:
- `channel` must reference a source channel with `dedup_required: false` - fixtures exercise `submit_record`'s implemented path, and intra-source dedup is still a `NotImplementedError` stub for `dedup_required: true` channels.
- Probabilistic-matching scenarios are out of scope for now, since the actual scoring algorithm is external to this project (see `MatchScorer` in `core/matching.py`) and fixtures have no way to express "call this external model."
