---
title: agrag.candidates.patch.endpoint_type
sidebar_label: endpoint_type
---

# `agrag.candidates.patch.endpoint_type` \{#agrag-candidates-patch-endpoint_type}

```python
endpoint_type(labels:Sequence[str], schema:GraphSchema) -> str | None
```

Select the most specific declared type among an entity's labels.

If multiple leaf types remain, the alphabetically first label is returned.

**Parameters:**

- **labels** (<code>Sequence\[str\]</code>) – Labels attached to an entity.
- **schema** (<code>[GraphSchema](../../common/data_models/graph_schema/GraphSchema.md)</code>) – Schema that declares entity types and their ancestry.

**Returns:**

- <code>str | None</code> – Selected schema type, or `None` when no label is declared.
