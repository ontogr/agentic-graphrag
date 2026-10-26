---
title: agrag.schema.shorthand.parse_relation
sidebar_label: parse_relation
---

# `agrag.schema.shorthand.parse_relation` \{#agrag-schema-shorthand-parse_relation}

```python
parse_relation(text:str) -> tuple[str, list[list[str]]] | None
```

Read `Source-LABEL->Target` text.

**Parameters:**

- **text** (<code>str</code>) – A relation string. `|` separates alternatives on either side.

**Returns:**

- <code>tuple\[str, list\[list\[str\]\]\] | None</code> – The relation label and the expanded `[source, target]` pairs, or
- <code>tuple\[str, list\[list\[str\]\]\] | None</code> – `None` when the text is not a relation string.
