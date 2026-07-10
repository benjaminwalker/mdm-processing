# Project Purpose
The end result will be some form of a master data management processing.

We want to have a configuration that can describe a domain model to participate in the master data management system.

Give a set of domain models, we want to be able to generate a relational model of the sources and master records that provides for auditability and traceability.

This should be an abstract framework that can easily be configuration driven and extensible, but provide a solid framework for any type of entity or data processing set.

It will ultimately be accessible via API (either via library or rest/graphql) for inputs and outputs, as well as part of batch processing systems (e.g. process a whole data set at once, vs receiving atomic input from API or streaming feed).

We want to keep things agnostic of physical storage medium, although we can assume that we'll have some permutations of relational database systems and things like S3/Iceberg, as well as commercial data solutions.  For the iterative development we'll focus initially on postgresql, but keep things behind and abstraction layer so the actual implementation doesn't bleed into the core logic.

So the first pass would be having configuration driven set of entity models to master, our code we develop, and a set of test cases that take some fixture sets and execute our logic against it.

Utlimately this library / set of code we'll port into multiple languages, but we'll start with Python.  Portability is achieved at the contract level, not the code-style level: we define the external-facing API (the mastery service's entry points - get by source record, get by ID, get by ID as-of, submit record) and the entity config format as language-agnostic contracts, and let each language implementation satisfy them however is idiomatic for that language. Internal implementation code (Python or otherwise) is not constrained to be "portable-looking" - only the contract is fixed.

The contract is enforced two ways:
- A documented API spec (request/response shapes and semantics for each entry point) rather than a schema-first/codegen approach (OpenAPI/protobuf) for now - lower overhead while we're Python-only.
- A fixture-driven conformance suite: input records + config in, expected master record output out. Runnable against any language's implementation to verify it honors the contract regardless of internal design.

The entity config format stays informal (plain YAML/JSON validated Python-side, e.g. via Pydantic) until a second language implementation actually needs to consume it - at that point it gets formalized (e.g. JSON Schema) rather than speculatively now.

## Personal Project Driver
While not a design focus for this project, my personal intent is to use this to ingest various wiki sources to provide for a comprehensive record of historical figures and their activities, so being able to process identity and data mastering for people, places, and things is important.