---
title: agrag.schema.shorthand.read_entities
sidebar_label: read_entities
---

# `agrag.schema.shorthand.read_entities` \{#agrag-schema-shorthand-read_entities}

```python
read_entities(value:object, path:str, issues:Issues) -> list[Draft]
```

Read the `entities` value in any accepted form.

**Parameters:**

- **value** (<code>object</code>) – A list of labels or objects, or a mapping from label to a
  description, `None` or an object.
- **path** (<code>str</code>) – The path of `value` in the source.
- **issues** (<code>[Issues](../errors/Issues.md)</code>) – Receives every problem found.

**Returns:**

- <code>list\[[Draft](Draft.md)\]</code> – One draft for each readable entity type, in source order.
