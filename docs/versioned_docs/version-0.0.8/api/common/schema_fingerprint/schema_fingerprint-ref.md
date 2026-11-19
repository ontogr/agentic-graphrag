---
title: agrag.common.schema_fingerprint.schema_fingerprint
sidebar_label: schema_fingerprint
---

# `agrag.common.schema_fingerprint.schema_fingerprint` \{#agrag-common-schema_fingerprint-schema_fingerprint}

```python
schema_fingerprint(schema:GraphSchema) -> str
```

Return the hash of the structure of a schema.

The hash covers entity types, parents, properties (type, required, enum),
relations, patterns, cardinality and symmetry. It ignores every description,
the schema name and the schema version, and the order of entities, relations,
patterns, parents and enum values.

**Parameters:**

- **schema** (<code>[GraphSchema](../data_models/graph_schema/GraphSchema.md)</code>) – The schema to hash.

**Returns:**

- <code>str</code> – The first 16 hex characters of the SHA-256 of the canonical structure.
