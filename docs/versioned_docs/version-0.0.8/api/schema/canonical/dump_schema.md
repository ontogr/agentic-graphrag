---
title: agrag.schema.canonical.dump_schema
sidebar_label: dump_schema
---

# `agrag.schema.canonical.dump_schema` \{#agrag-schema-canonical-dump_schema}

```python
dump_schema(schema:GraphSchema) -> dict[str, Any]
```

Return the canonical dict form of a schema.

The canonical form holds every field, with no shorthand. Entity and
relation order is kept, and each relation pattern is a `[source, target]`
list. `load_schema(dump_schema(schema)) == schema` for every valid
schema, and the dump is plain JSON data.

**Parameters:**

- **schema** (<code>[GraphSchema](../../common/data_models/graph_schema/GraphSchema.md)</code>) – The schema to dump.

**Returns:**

- <code>dict\[str, Any\]</code> – A new dict that the caller may change freely.
