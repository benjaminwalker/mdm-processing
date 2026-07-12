# mdm-processing

A configuration-driven Master Data Management (MDM) library. It resolves entity records contributed by multiple source systems into a single, best-known master representation, tracking exactly which source contributed each winning value and why.

## What it does

- **Config-driven entity modeling** - entity types (natural keys, optional probabilistic candidate keys, per-attribute TTLs) and source channels (precedence ranking, dedup policy) are declared as YAML, not code. See [`docs/config_format.md`](docs/config_format.md).
- **Identity resolution** - incoming records are matched to existing master records deterministically (exact natural-key equality) first, with an optional probabilistic fallback for entity types that define one. Conflicting matches are surfaced rather than silently guessed at.
- **Pluggable probabilistic matching** - the actual scoring algorithm is intentionally kept outside this project. You supply a scorer function (plain data in, similarity score out), which can wrap anything from a simple heuristic to an external ML model.
- **Survivorship** - when multiple sources disagree on an attribute's value, resolution happens in two stages: first the most recent value *within* each contributing channel, then across channels by precedence - except for attributes with a configured TTL, where recency overrides precedence outright.
- **Full attribute recomputation** - a master's attributes can be rebuilt from every source currently contributing to it, not just the record that happened to trigger the update.
- **Auditable by design** - every source record and master record carries audit metadata (timestamp, author, batch id), and master records track their own creation time separately from their last-modified time.
- **Point-in-time-ready data model** - master records that get superseded (merged into another) are never deleted, just tombstoned with a pointer to the survivor, which read APIs follow transparently, including through multi-hop chains.

## API surface

The service is defined as a language-agnostic contract - request/response shapes and semantics, independent of transport or implementation language - so future non-Python implementations can satisfy the same contract without needing to look like the Python code. See [`docs/api_contract.md`](docs/api_contract.md) for the full entry point list (record submission, batch submission, and master record reads).

## Conformance fixtures

Behavior is captured as data, not just unit tests: YAML fixtures describe a sequence of record submissions against a given entity/channel config and assert the resulting outcomes. These are meant to be runnable against any implementation of the contract, not just the Python one. See [`docs/fixture_format.md`](docs/fixture_format.md).

## Repository layout

```
docs/            language-agnostic API contract, config format, and fixture format docs
config/          example entity/source-channel YAML definitions
fixtures/        conformance fixtures exercising those configs end to end
python/          the Python implementation (pyproject.toml, src/, tests/)
```

`docs/`, `config/`, and `fixtures/` are the shared, portable parts of the project; `python/` is one implementation of the contract they describe.

## Status

**Implemented**: entity/channel config validation, the reprocessing (checksum-based no-op/new-version) check, deterministic and probabilistic cross-channel matching, two-stage survivorship resolution, full master-attribute recomputation across all current contributors, an in-memory storage backend, and synchronous master record reads by source record and by ID (the latter transparently resolving through any superseded-master redirect chain).

**Not yet implemented**: intra-source duplicate detection (stubbed - raises clearly rather than guessing), automatic merging of masters discovered to share a natural key, the asynchronous batch submission entry points, point-in-time ("as of") master record reconstruction, and a persistent (e.g. Postgres) storage backend.

## Getting started

The Python implementation is managed with [`uv`](https://docs.astral.sh/uv/), from the `python/` directory:

```
cd python
uv sync
uv run pytest
```
