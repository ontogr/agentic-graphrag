---
title: agrag.schema.shorthand.split_list
sidebar_label: split_list
---

# `agrag.schema.shorthand.split_list` \{#agrag-schema-shorthand-split_list}

```python
split_list(items:Sequence[object], issues:Issues) -> JsonObject
```

Split a native list into entity labels and relations.

**Parameters:**

- **items** (<code>Sequence\[object\]</code>) – Labels, `Source-LABEL->Target` strings and `(source, label, target)` triples, in any order.
- **issues** (<code>[Issues](../errors/Issues.md)</code>) – Receives every item that is none of these.

**Returns:**

- <code>[JsonObject](JsonObject.md)</code> – A dict with the keys `entities` and `relations`.
