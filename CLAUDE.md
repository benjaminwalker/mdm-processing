# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

This repository is early-stage: the domain spec and architecture are written, but application code is just being scaffolded. Read these two files before implementing anything — they are the source of truth:

- `data_processing.md` — the MDM domain specification (entities, source channels, mastery registry, matching, precedence). Contains explicit **"Open question, not yet decided"** callouts for design points that haven't been resolved (e.g. merge-survivor selection, redirect-chain handling, unmerge/split, overlapping valid-period reconciliation, deletion/tombstone handling). Check these before assuming behavior in an unresolved area — flag it rather than silently picking a design.
- `project_purpose.md` — why the project exists and the architectural principles it must follow (see below).

## Repo layout

This repo is structured for eventual multi-language ports, not just the current Python implementation:

```
docs/            shared, language-agnostic API contract + config format docs
config/          shared entity/source-channel definitions (YAML) - see docs/config_format.md
fixtures/        shared conformance test data (input records + config -> expected master record output)
python/          the Python implementation - pyproject.toml, src/, tests/, .venv all live here
```

`docs/` and `fixtures/` are the portable contract; `python/` is one implementation of it. Don't assume the repo root is the Python project root — it's `python/`.

## Architecture principles (from project_purpose.md)

- **Portability is a contract, not a code style.** The external API (get master record by source record / by ID / by ID as-of / submit record) and the entity config format are the language-agnostic contracts. Internal Python code should be as idiomatic as makes sense — it is *not* constrained to look "portable." A future language port satisfies the same contract however is natural for that language.
- **Contract enforcement**: a documented API spec (`docs/api_contract.md`, not yet written) plus a fixture-driven conformance suite (`fixtures/`) — not schema-first/codegen tooling (no OpenAPI/protobuf for now).
- **Config-driven**: entity/source-channel definitions are data (YAML/JSON, Pydantic-validated on the Python side), not hardcoded. The config format stays informal until a second language implementation needs to consume it.
- **Storage-agnostic core**: mastering logic (identity resolution, precedence/survivorship, valid-period handling) must not know which storage backend it's running against. Storage-specific code lives behind an adapter (e.g. `storage/postgres/`); Postgres is the first target, S3/Iceberg and commercial MDM stores are anticipated later.
- **One code path for both consumption modes**: batch processing is an orchestration loop around the same record-at-a-time primitives used by the atomic API/library path — not a separate implementation.

## Environment (python/)

- Python >=3.13, managed with `uv`. All commands below run from `python/`.
- `uv add <package>` to add a runtime dependency, `uv add --dev <package>` for dev-only, `uv run <cmd>` to execute code/tests in the project environment — don't invoke `pip`/`python` directly.
- `uv run pytest` runs the test suite (pytest is configured as a dev dependency).
- Current dependencies: `pydantic`, `pyyaml` (runtime); `pytest` (dev).

## Domain model (from data_processing.md)

This project implements **Master Data Management (MDM)**: resolving entity records from multiple source systems into a single master representation.

- **MDM Entity**: conforms to an agreed-upon domain model, with declared **natural keys** (immutable, deterministic identity attributes like SSN or email) and optional **candidate keys** (attributes used for probabilistic matching, e.g. name+DOB+address) plus a match strategy. Candidate keys are optional per entity type — some entities are matched deterministically only. Attributes may carry a **TTL**, which overrides channel precedence for survivorship when configured (recency wins over rank).
- **Source Channel**: a system of record supplying data for one or more entities, with a precedence ranking for survivorship (default, overridden by attribute TTL when present) and its own intra-source dedup config (`dedup_required`, `dedup_strategy`) — separate from cross-channel matching.
- **Source reference key**: the `(source channel code, source key name, source key value)` tuple — a foreign-key reference back to a record's primary key in its source system. Distinct from an entity's natural key (domain identity attribute vs. row identity).
- **Mastery Registry**: two tables — a master record table and a crosswalk table (source reference key → master key), so `Get Master Record by Source Record` is a direct indexed lookup. Master record IDs are **not immutable**: on merge, crosswalk rows are re-pointed to the survivor and the superseded master row is retained as a tombstone pointing at the survivor.
- **Three API entry points**: get by source reference key, get by master ID, get by master ID as-of a point in time (reconstructed from valid-period history).

### Processing pipeline (two phases)

1. **Within a source channel**: (a) reprocessing check — same source reference key seen before → checksum compare → no-op or new row version; (b) intra-source duplicate check — only if the channel requires it, via that channel's own dedup strategy, independent of cross-channel matching.
2. **Across source channels**: match per the entity type's strategy — deterministic natural-key match first, then probabilistic candidate-key matching as a fallback only if the entity type defines one.

### Metadata conventions

- **Audit columns** (`metadata_audit_timestamp`, `metadata_audit_author`, `metadata_audit_batch_id`) record physical write time and provenance only.
- **Data change / validity columns** are a separate SCD-Type-2-style concept representing domain-time validity. Precedence: explicit data change columns from the source if present, otherwise audit columns.
