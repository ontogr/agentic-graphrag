---
title: agrag.candidates.patch.declares_property
sidebar_label: declares_property
---

# `agrag.candidates.patch.declares_property` \{#agrag-candidates-patch-declares_property}

```python
declares_property(schema:GraphSchema, entity_label:str, name:str) -> bool
```

Check whether an entity type or an ancestor declares a property.

**Parameters:**

- **schema** (<code>[GraphSchema](../../common/data_models/graph_schema/GraphSchema.md)</code>) – Schema containing entity definitions.
- **entity_label** (<code>str</code>) – Entity type to check.
- **name** (<code>str</code>) – Property name to find.

**Returns:**

- <code>bool</code> – Whether the type or any declared ancestor defines the property.
