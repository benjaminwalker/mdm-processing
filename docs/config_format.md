# Entity & Source Channel Config Format

YAML, one file per entity type and one file per source channel (see `project_purpose.md` / `CLAUDE.md` for why: this config is part of the language-agnostic contract, kept informal - no formal schema artifact yet - until a second language implementation needs to consume it; see `data_processing.md` for the domain concepts these fields encode).

Layout:
```
config/
  entities/
    <entity_type>.yaml
  source_channels/
    <channel_code>.yaml
```

## Entity file (`config/entities/<entity_type>.yaml`)

```yaml
entity_type: customer
description: A person who purchases goods or services from the business.

natural_keys:
  - ssn
  - email
  - phone

candidate_keys:
  match_strategy: probabilistic_v1
  threshold: 0.85
  attributes:
    - name
    - date_of_birth
    - address

attributes:
  - name: ssn
    type: string
  - name: email
    type: string
  - name: phone
    type: string
  - name: name
    type: string
  - name: date_of_birth
    type: date
  - name: address
    type: string
    ttl: P90D
```

Field notes:
- `natural_keys` / `candidate_keys.attributes` are lists of names referencing entries in `attributes` - not redefined inline, to avoid duplicating type info.
- `candidate_keys` is optional. An entity type with no `candidate_keys` block is matched deterministically only (see `docs/api_contract.md` - Cross-channel match outcome).
- `match_strategy` is a string identifier, not an inline algorithm - it names a strategy the core code resolves to an implementation. Config carries *which* strategy and its parameters (e.g. `threshold`), not the matching logic itself.
- `type` is one of: `string`, `integer`, `decimal`, `boolean`, `date`, `datetime`. (Minimal set for now - extend as real entity types need more.)
- `ttl`, where present on an attribute, is an ISO 8601 duration (e.g. `P90D` = 90 days). Overrides channel precedence for survivorship on that attribute (see `data_processing.md` - MDM Entities).

## Source channel file (`config/source_channels/<channel_code>.yaml`)

```yaml
channel_code: crm_salesforce
description: Primary CRM system of record for customer contacts.
precedence: 1

dedup_required: true
dedup_strategy: crm_dedup_v1
```

Field notes:
- `precedence` is a numeric rank, `1` = highest. Ranks don't need to be contiguous - leave gaps (10, 20, 30, ...) to make room for inserting a channel between two existing ones later.
- `dedup_required` / `dedup_strategy` are independent of `candidate_keys`/`match_strategy` above - intra-source dedup and cross-channel matching are separate concerns (see `data_processing.md` - Mastery within Source Channels). `dedup_strategy` follows the same "named identifier resolved by code" pattern as `match_strategy`.

## Not yet decided
- Validation is Pydantic-side only for now (see `python/src/mdm_processing/config/`, not yet implemented) - no standalone schema artifact.
- No versioning scheme for config files yet (e.g. what happens to already-mastered data when an entity's `attributes` or `natural_keys` change).
