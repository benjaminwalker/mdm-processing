# Rules of MDM
Master Data Management involves taking entity objects with identity and resolving from multiple sources to represent a single, master record representation of an identified entity.

## Example of MDM
A business has multiple lines of business each with their own representation of a customer, and within downstream contexts those representations need to be unified to present the best known representation.
An object or entity has characteristics drawn from multiple sources e.g.
- a user enters an address, and an address resolution service provides alternative representations of the address, but both are desired to be preserved
- using more than one source of data enhancement where you may have multiple data sets describing something that is the same in the domain model.

## MDM Entities
Data presented for MDM should represent the agreed upon common Domain Model for that particular type of entity.  This should represent the broad, complete set of attributes and characteristics that can describe the entity.

An entity model presented to the mastery process should also have natural keys identified, as well as candidate keys.  In this case a natural key is some immutable identity artifact that has no probabilistic nature, such as as social security number, email address, phone number in the case of a person, a parcel number or address for a property. The natural keys will indicate what fields are explicitly available for the identity resolution process.

Candidate keys are the attributes used for *probabilistic* matching (e.g. name + date of birth + address for a person) when two records don't share an exact natural-key value. Candidate keys, and the scoring strategy/threshold that uses them, are optional per entity type - some entity types may only ever be matched deterministically on natural keys, with no probabilistic capability defined at all.

So a MDM entity registry would have something like
'domain object name', 'description', [list of natural keys], [list of candidate keys + match strategy, optional], [data cols]

In addition, it should also be possible to tag specific attributes as having a TTL.  In certain cases, having recent data from an unreliable source is much better than stale data from a reliable source.  An attribute level TTL can provide indicators to the mastery process to take this into account.

TTL overrides channel precedence when both apply to the same attribute: if the attribute has a TTL configured, survivorship for that attribute is decided by recency (most recent value wins, regardless of the contributing channels' precedence ranking). If the attribute has no TTL configured, survivorship falls back to the default: the value from the highest-precedence contributing channel wins (see Source Channels).

## Source Channels
A source of data, either one time, periodic, stream, or API driven, that is contextually from the same system of record.

Each source channel should have characteristics to help drive the mastery process, with some value assigned to assert precedence.  This can either be an assigned value e.g. HIGHEST or 1 vs LOWEST or 5, any sort of indicator that can be stack ranked.  This is usually based upon an overall assertion of the quality of data from the source channel. This is the default survivorship rule for an attribute; it is overridden by attribute-level TTL when one is configured (see MDM Entities).

Each source channel also declares its own intra-source duplicate handling, independent of the cross-channel matching strategy:
- `dedup_required` - whether this channel can emit multiple records for the same real-world entity under different keys (true), or is already guaranteed unique per entity (false, e.g. a system with an enforced uniqueness constraint), in which case intra-source dedup is skipped entirely.
- `dedup_strategy` - the channel-specific rule set used to detect and resolve duplicates when `dedup_required` is true. This is configured per channel and may differ from channel to channel, and from the strategy used for cross-channel matching.

## Mastery Registry
The mastery registry is a key store that links all records to their definitive master record. It is made up of two tables:

- **Master record table**: `master key, entity type (domain), [entity attributes]`. One row per mastered entity.
- **Crosswalk table**: `source channel code, source key name, source key value, master key`. One row per source reference key, pointing at the master key it currently resolves to. Independently indexed on the source reference key so `Get Master Record by Source Record` (below) is a direct lookup.

(Starting with two tables and a crosswalk pattern rather than embedding source reference keys as a repeating group directly on the master record. Worth revisiting once the storage engine is chosen - if source-reference-key cardinality per master stays small and mostly static and the engine is document-oriented, a denormalized array could eliminate the join.)

A master record id is not immutable and may be superseded by operations over time. For instance, we may have two master records, but over time may receive a new data source that through the identity process links two master records, causing what was thought to be a new master record.

In these cases, the crosswalk rows for the superseded master are re-pointed to the surviving master key. The superseded master record row is retained (not deleted) as a tombstone carrying a pointer to the surviving master key, so the mastery registry can indicate a pointer to the new master record and return the values associated with it.

**Open questions, not yet decided:**
- How is the surviving master key chosen when two masters merge (oldest key, highest-precedence contributing source, or some other rule)?
- How are multi-hop redirect chains handled (master A superseded by B, later B superseded by C) - is a lookup on A expected to chase multiple hops, or are chains collapsed/flattened at merge time so any pointer is always at most one hop from the current survivor?
- Is there a supported "unmerge" / split operation for correcting a false-positive match, and if so what does it do to the crosswalk rows and any master-level data that was combined during the incorrect merge?

From an API aspect there are three entry points to a master record:
Get Master Record by Source Record
- this takes in the tuple of 3 (source channel, source key name, source key value) and returns a master record
Get Master Record by ID
- for use cases that have a representation of a master record id, this returns the master record
Get Master Record by ID as of a point in time
- returns the master record as it existed at a given timestamp, reconstructed from the SCD2-style valid-period history (see Data Change Columns)

### Mastery within Source Channels
Duplicate detection *within* a single source is a channel-specific concern, not a rescoped version of cross-channel matching. Each channel declares whether it requires dedup (`dedup_required`) and, if so, which channel-specific strategy to apply (`dedup_strategy`). Channels that already guarantee one record per real-world entity can skip this step entirely.

The cross-channel mastery process (see below) only ever operates on already-deduplicated, one-record-per-entity output from each channel - it never has to reason about intra-source duplicates itself.

## MDM Processing
Processing data into a master data management system relies on two principles, identity resolution and data precedence.  If we determine that two source of information are describing the same entity, we must determine which attributes have more truth.

Record submitted for mastery process, from a source.
# Within Source Channels
Checks per record, in order:
1. **Reprocessing check** - has this exact record (same source channel + source key) been processed before?
   - If yes and checksums match: no-op (write a no-op audit log record if extended auditing is enabled).
   - If yes and checksums differ: create a new row version with appropriate valid periods.
   - If no: treat as a new record for this source key and create a new entry.
2. **Intra-source duplicate check** - only performed if the channel's `dedup_required` is true: does this record (new or updated) match an existing record in the same source under a *different* key, per the channel's `dedup_strategy`?
   - If a match is found, link the records as the same entity within the source before this channel's output is passed to cross-channel mastery.
   - If no match, the record proceeds standalone.

# Across Source Channels
The mastery process will take the deduplicated inputs from all source channels and, per identified entity, create a representation of the data taking all channel sources into account.

Matching across channels follows the entity type's configured match strategy (see MDM Entities):
1. **Deterministic match** - attempt to match on exact natural-key value equality first. This is always attempted, since natural keys are required for every entity type.
2. **Probabilistic fallback** - only if the entity type defines candidate keys and a match strategy: for records with no natural-key overlap, score candidate pairs using the entity type's probabilistic strategy and link them if the score meets the configured threshold. Entity types with no candidate keys defined skip this step entirely and rely on deterministic matching alone.

The resulting master record's attributes carry their own validity periods, derived per the rules in Data Change Columns below.

# Source Metadata

## Source Lineage
Source Channel - where did the data come from
Source Key Name - the key that is the description, column name, field name, etc describing the provenance of the value
Source Key Value - the unique key or identifier within the source data set that provides identity

## Audit Columns
We maintain an audit registry of when data is written.  This represents the physical time period the data was present in the database
and available for downstream processing, it does not represent anything beyond that in and of itself.

Audit columns will be
- metadata_audit_timestamp
- metadata_audit_author
- metadata_audit_batch_id - identifies the specific processing run/job that wrote the row, to aid debugging when a source is reprocessed (see "Data may be reprocessed within a channel" below)

**Open question, not yet decided:** how are deletions/retirements handled - if a source system retires a record, or a master record is fully retired, is there a tombstone representation, and how does that interact with valid periods and the crosswalk?

## Data Change Columns
Separate from audit columns, we have a domain concept of data validity periods.  Similar to an SCD type 2 record, we
provide the functionality to present a lineage of change.  This must be interpreted from the data submitted (e.g. if it has a time period associated with it, such as a monthly or annual data feed / pull, or a modified / created timestamp).
This is transformed into a representation of a valid period.

The precedence for valid period will be explicit data change columns, if present, otherwise audit columns.

**Open question, not yet decided:** when two sources report conflicting or overlapping valid periods for the same master attribute (e.g. Source A says an address is valid Jan-Jun, Source B says the same field is valid Feb-Aug), how is the master's valid period resolved - does the survivorship winner's period simply replace the loser's outright, or are periods merged/reconciled in some other way?



So a typical row would look like
- primary key (of table), 
- data columns, 
- src_channel_cd, 
- src_key_name, 
- src_key_value

The combination of these three attributes forms the **source reference key** - a foreign-key reference back to the record's primary key in its source system of record. This is distinct from an entity's natural key (see MDM Entities): the source reference key identifies a physical row/record, while a natural key is a domain-level identity attribute of the entity itself (e.g. SSN). The source reference key is unique across all data sets and is what `Get Master Record by Source Record` (see Mastery Registry) takes as input.

Data may be reprocessed within a channel.  I.e. if we load a CSV from x data source, then reload the same CSV or an updated CSV from the same source, that data should be reconciled against previous knowledge from that source prior to joining the master data set.

