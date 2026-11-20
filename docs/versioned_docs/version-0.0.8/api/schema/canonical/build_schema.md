---
title: agrag.schema.canonical.build_schema
sidebar_label: build_schema
---

# `agrag.schema.canonical.build_schema` \{#agrag-schema-canonical-build_schema}

```python
build_schema(data:dict[str, Any], origins:Mapping[str, list[str]], issues:Issues) -> GraphSchema | None
```

Validate a canonical dict and map model errors back to source paths.

**Parameters:**

- **data** (<code>dict\[str, Any\]</code>) – A canonical dict.
- **origins** (<code>Mapping\[str, list\[str\]\]</code>) – For `entities` and `relations`, the source path of each
  item in `data`, in the same order.
- **issues** (<code>[Issues](../errors/Issues.md)</code>) – Receives one issue per model error.

**Returns:**

- <code>[GraphSchema](../../common/data_models/graph_schema/GraphSchema.md) | None</code> – The schema, or `None` when the model rejects `data`.
