---
title: agrag.schema.shorthand.read_relations
sidebar_label: read_relations
---

# `agrag.schema.shorthand.read_relations` \{#agrag-schema-shorthand-read_relations}

```python
read_relations(value:object, path:str, issues:Issues) -> list[Draft]
```

Read the `relations` value in any accepted form.

**Parameters:**

- **value** (<code>object</code>) – A list of `Source-LABEL->Target` strings, `(source, label, target)` triples and objects, or a mapping from label to patterns
  or to an object.
- **path** (<code>str</code>) – The path of `value` in the source.
- **issues** (<code>[Issues](../errors/Issues.md)</code>) – Receives every problem found.

**Returns:**

- <code>list\[[Draft](Draft.md)\]</code> – One draft for each readable relation type, in source order. Strings and
- <code>list\[[Draft](Draft.md)\]</code> – triples with the same label share one draft.
