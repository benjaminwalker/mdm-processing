# MDM Mastery Service - API Contract

This is the language-agnostic contract for the mastery service. It describes each entry point's request/response shape and semantics, independent of transport (library call, REST, gRPC, etc.) and independent of implementation language. Any implementation - Python or otherwise - satisfies this document however is idiomatic for that language; only the shapes and behavior described here are fixed.

This is a first pass and is expected to change as the domain model in `data_processing.md` firms up. Sections marked **Open question** describe behavior not yet decided; implementations should surface these as explicit TODOs rather than silently picking a behavior.

Conventions: fields are named in `snake_case`. Types are described abstractly (string, timestamp, map, list, enum) rather than in any one language's type system.

## Common shapes

### Source Reference Key
Identifies a single record within a single source channel. See `data_processing.md`.
```
source_reference_key:
  source_channel_cd: string
  source_key_name:   string
  source_key_value:  string
```

### Record (submission input)
The shape submitted to the service for mastering, for both the sync and async/batch submit entry points.
```
record:
  entity_type:           string              # domain object name, per the entity registry
  source_reference_key:  SourceReferenceKey
  attributes:             map<string, value>  # raw data columns for this entity type
  change_timestamp:       timestamp | null    # source-provided modified/effective time, if available (see Data Change Columns)
  audit_author:           string              # who/what submitted this record
```

### Attribute (on a master record)
A single mastered attribute value, with the provenance and validity period that produced it.
```
attribute:
  name:                  string
  value:                 value
  valid_from:            timestamp
  valid_to:              timestamp | null     # null = currently valid
  winning_source:        SourceReferenceKey   # which source's value survived to become this attribute
```

### Master Record
```
master_record:
  master_key:            string
  entity_type:            string
  attributes:              list<Attribute>
  resolved_from:           string | null      # populated only when the caller requested a since-superseded master_key; holds that original key
```

### Within-channel outcome (enum)
Result of the reprocessing + intra-source dedup checks (`data_processing.md` - Within Source Channels).
```
no_op                    # exact reprocess of unchanged data
new_version               # same source reference key, changed data
new_record                 # source reference key not seen before
linked_intra_source_duplicate   # matched an existing record in the same source under a different key (dedup_strategy)
```

### Cross-channel match outcome (enum)
Result of matching this record against existing master records (`data_processing.md` - Across Source Channels).
```
master_created                    # no match found; new master record created
master_matched_deterministic      # matched an existing master via natural-key equality
master_matched_probabilistic      # matched an existing master via candidate-key scoring
```

## Entry points

### 1. Submit Record (synchronous)
Single atomic record in, fully mastered record out. Runs both processing phases (within-channel, then across-channel) before returning.

**Request**: one `Record`.

**Response**:
```
source_reference_key:      SourceReferenceKey
within_channel_outcome:     WithinChannelOutcome
cross_channel_outcome:      CrossChannelOutcome
master_record:               MasterRecord
```

**Semantics**: this is the primitive both the atomic API and batch processing are built on (per `project_purpose.md`) - `Submit Batch` below is this same operation, looped, run asynchronously.

### 2. Submit Batch (asynchronous)
Accepts many records for mastering without blocking on completion.

**Request**:
```
records: list<Record>
```

**Response** (immediate, does not wait for processing):
```
batch_id: string
status:    "accepted"
```

**Semantics**: each record in the batch is processed via the same logic as `Submit Record`, independently. A caller retrieves outcomes via `Get Batch Status` and, for individual records, `Get Master Record by Source Record` using the source reference keys it already submitted.

### 3. Get Batch Status
Poll a previously submitted batch for progress.

**Request**:
```
batch_id: string
```

**Response**:
```
batch_id:    string
status:       "queued" | "processing" | "complete" | "failed"
total:         integer
succeeded:     integer
failed:        integer
```

**Semantics**: intentionally returns counts only, not per-record results - the caller already knows the source reference keys it submitted and re-fetches individual masters via entry point 4. **Open question**: how does a caller identify *which* records failed, beyond the failure count? A follow-up "Get Batch Errors" entry point may be needed once error-handling requirements are clearer.

### 4. Get Master Record by Source Record
**Request**: one `SourceReferenceKey`.

**Response**: one `MasterRecord`, or not-found.

### 5. Get Master Record by ID
**Request**:
```
master_key: string
```

**Response**: one `MasterRecord`, or not-found.

**Semantics**: if `master_key` refers to a master record that has since been superseded (merged into another), this transparently resolves to the surviving master record. The response's `resolved_from` field is set to the originally requested `master_key` so the caller knows a redirect happened.

### 6. Get Master Record by ID, as of a point in time
**Request**:
```
master_key: string
as_of:       timestamp
```

**Response**: one `MasterRecord`, reconstructed from valid-period history as it existed at `as_of` (see Data Change Columns in `data_processing.md`), or not-found if the master did not exist at that time.

**Semantics**: follows the same superseded-ID resolution as entry point 5. **Open question**: when `master_key` was later merged into a survivor, and `as_of` predates the merge, should this return the pre-merge entity's state at that time, or the survivor's reconstructed state at that time (which may include data contributed by what was, at `as_of`, still a separate master)? Not yet decided.

## Open questions summary
- Batch-level failure detail retrieval (per entry point 3)
- As-of semantics across a merge boundary (per entry point 6)
- These compound the open questions already tracked in `data_processing.md` (merge-survivor selection, redirect-chain handling, unmerge/split, overlapping valid-period reconciliation, deletion/tombstone handling) - all of which shape these entry points' exact behavior once resolved.
