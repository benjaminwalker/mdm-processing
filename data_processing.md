# Rules of MDM
Master Data Management involes taking entity objects with identity and resolving from multipl sources to represent a single, master record representation of an identified entity.

## Example of MDM
A business has multiple lines of business each with their own representation of a customer, and within downstream contexts those representations need to be unified to present the best known representation.
An object or entity has characteristics drawn from multiple sources e.g.
- a user enters an address, and an address resolution service provides alternative representations of the address, but both are desired to be preserved
- using more than one source of data enhancement where you may have multiple data sets describing something that is the same in the domain model.

## MDM Entities
Data presented for MDM should represent the agreed upon common Domain Model for that particular type of entity.  This should represent the broad, complete set of attributes and characteristics that can describe the entity.

An entity model presented to the mastery process should also have natural keys identified, as well as candidate keys.  In this case a natural key is some immutable identity artifact that has no probabilistic nature, such as as social security number, email address, phone number in the case of a person, a parcel number or address for a property. The natural keys will indicate what fields are explicitly available for the identity resolution process.

So a MDM entity registry would have something like
'domain object name', 'description', [list of natural keys], [data cols]

In addition, it should also be possible to tag specific attributes as having a TTL.  In certain cases, having recent data from an unreliable source is much better than stale data from a reliable source.  An attribute level TTL can provide indicators to the mastery process to take this into account.

## Source Channels
A source of data, either one time, periodic, stream, or API driven, that is contextually from the same system of record.

Each source channel should have characteristics to help drive the mastery process, with some value assigned to assert precedence.  This can either be an assigned value e.g. HIGHEST or 1 vs LOWEST or 5, any sort of indicator that can be stack ranked.  This is usually based upon an overall assertion of the quality of data from the source channel.

## Mastery Registry
The mastery registry is a key store that links all records to their definitive master record.
A representation of this as a data model would be

master key, entity type (domain),related key (entity key), source channel values(source channel code, source key name, source key value).

A master record id is not immutable and may be superseded by operations over time. For instance, we may have two master records, but over time may receive a new data source that through the identity process links two master records, causing what was thought to be a new master record.

In these cases, the mastery registry must be able to indicate a pointer to the new master record, and return the values associated with the new master record.

From an API aspect there are two entry points to a master record:
Get Master Record by Source Record
- this takes in the tuple of 3 (source channel, source key name, source key value) and returns a master record
Get Master Record by ID
- for use cases that have a representation of a master record id, this returns the master record

### Mastery within Source Channels
This is tricky, if we detect logical duplicates within a source

## MDM Processing
Processing data into a master data management system relies on two principles, identity resolution and data precedence.  If we determine that two source of information are describing the same entity, we must determine which attributes have more truth.

Record submitted for mastery process, from a source.
# Within Source Channels
Checks per record
- identity resolution
  - is this a logical duplicate of an existing record in source (natural keys or probabilistic duplication)
    - if duplicate in source
- has this record been processed before (do the source channel and key attributes match)
  - if so, is this an update with different data (do checksums differ) or is it reprocessing the same data
    - if same data, no-op, and if extended auditing present, write no-op row audit log record.
    - if updated data, create a new row version with appropriate valid periods
  - if a new new record, create new entry.

# Across Source Channels
The mastery process will take the inputs from all source channels, and per identified entity create a representation of the data taking all channel sources into account.  This master record will have validity

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

## Data Change Columns
Separate from audit columns, we have a domain concept of data validity periods.  Similar to an SCD type 2 record, we
provide the functionality to present a lineage of change.  This must be interpreted from the data submitted (e.g. if it has a time period associated with it, such as a monthly or annual data feed / pull, or a modified / created timestamp).
This is transformed into a representation of a valid period.

The precedence for valid period will be explicit data change columns, if present, otherwise audit columns.



So a typical row would look like
- primary key (of table), 
- data columns, 
- src_channel_cd, 
- src_key_name, 
- src_key_value

The combination of these three attributes provides for the natural key across all data sets.

Data may be reprocessed within a channel.  I.e. if we load a CSV from x data source, then reload the same CSV or an updated CSV from the same source, that data should be reconciled against previous knowledge from that source prior to joining the master data set.

