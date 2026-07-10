# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

This repository is greenfield: `pyproject.toml` declares no dependencies yet and no application code has been written. The only substantive content is `data_processing.md`, the domain specification for the system to be built. Read that file before implementing anything — it is the source of truth for terminology and behavior described below.

## Environment

- Python >=3.13, managed with `uv` (a `.venv` created by uv is already present).
- Use `uv add <package>` to add dependencies and `uv run <cmd>` to execute code/tests within the project environment, rather than invoking `pip`/`python` directly.
- No test framework, linter, or build tooling is configured yet — check `pyproject.toml` before assuming a command (e.g. `pytest`) is available.

## Domain model (from data_processing.md)

This project implements **Master Data Management (MDM)**: resolving entity records from multiple source systems into a single master representation. Key concepts future code will be organized around:

- **MDM Entity**: a record conforming to an agreed-upon common domain model, with declared **natural keys** (immutable, deterministic identifiers like SSN or email) and candidate keys used for identity resolution. Attributes may carry a **TTL**, since recent low-quality data can outrank stale high-quality data.
- **Source Channel**: a system of record (batch, stream, or API) that supplies data for one or more entities. Each channel has a precedence/quality ranking used to resolve conflicting attribute values across sources.
- **Mastery Registry**: the key store mapping source records to master records. Represented conceptually as `master key, entity type, related key (entity key), source channel values (source channel code, source key name, source key value)`. Master record IDs are **not immutable** — two master records can later be discovered to be the same entity, requiring the registry to redirect the superseded ID to the surviving one.
- **Two lookup entry points**: get master record by `(source channel, source key name, source key value)`, and get master record by master ID.
- **Natural key for any row**: the combination of `src_channel_cd`, `src_key_name`, `src_key_value` (plus the table's own primary key and data columns).

### Processing pipeline (two phases)

1. **Within a source channel** — per incoming record: check whether it's a logical duplicate of an existing record in the same source (via natural keys or probabilistic matching); if it has been seen before, compare checksums to distinguish a no-op reprocess from an update (which creates a new row version with valid periods); otherwise insert as new.
2. **Across source channels** — the mastery process combines all source channels' records for an identified entity into the master record.

### Metadata conventions

- **Audit columns** (`metadata_audit_timestamp`, `metadata_audit_author`) record physical write time only.
- **Data change / validity columns** are a separate SCD-Type-2-style concept representing the domain-time validity period of a value. Precedence: use explicit data change columns from the source if present, otherwise fall back to audit columns.
