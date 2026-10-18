---
title: agrag.schema.shorthand.parse_pattern
sidebar_label: parse_pattern
---

# `agrag.schema.shorthand.parse_pattern` \{#agrag-schema-shorthand-parse_pattern}

```python
parse_pattern(text:str) -> list[list[str]] | None
```

Read `Source->Target` text into `[source, target]` pairs.

**Returns:**

- <code>list\[list\[str\]\] | None</code> – The expanded pairs, or `None` when the text has no arrow.
