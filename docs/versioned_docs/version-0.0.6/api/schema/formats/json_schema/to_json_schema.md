---
title: agrag.schema.formats.json_schema.to_json_schema
sidebar_label: to_json_schema
---

# `agrag.schema.formats.json_schema.to_json_schema` \{#agrag-schema-formats-json_schema-to_json_schema}

```python
to_json_schema(schema:GraphSchema) -> dict[str, Any]
```

Export a schema as a JSON Schema that checks a plain extraction document.

The result describes one document with an `entities` array and a
`relations` array. Each entity is `{"label", "text", "properties"}`.
Each relation is `{"type", "source", "target", "source_label", "target_label"}`. The allowed label pairs come from
`GraphSchema.allows`, so they cover child types and the reverse
direction of a symmetric relation. Parents, cardinality and symmetry have
no JSON Schema keyword, so they appear as `x-agrag-*` annotations that
validators ignore.

This is a plain interchange document for LLM structured output, not a
dump of `ExtractionResult` or the BAML extraction response. Those carry
chunk ids, character offsets, and index- or text-based endpoints that this
shape does not model.

**Parameters:**

- **schema** (<code>[GraphSchema](../../../common/data_models/graph_schema/GraphSchema.md)</code>) – The schema to export.

**Returns:**

- <code>dict\[str, Any\]</code> – A JSON-serializable dict. Serialize it with `json.dumps`.
