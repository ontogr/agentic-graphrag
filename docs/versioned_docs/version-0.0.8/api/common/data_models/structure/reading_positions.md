---
title: agrag.common.data_models.structure.reading_positions
sidebar_label: reading_positions
---

# `agrag.common.data_models.structure.reading_positions` \{#agrag-common-data_models-structure-reading_positions}

```python
reading_positions(document:Document) -> tuple[list[int], list[list[int]]]
```

Number every heading and unit of a document in reading order.

**Parameters:**

- **document** (<code>[Document](../document/Document-ref.md)</code>) – The document.

**Returns:**

- <code>tuple\[list\[int\], list\[list\[int\]\]\]</code> – The position of each section heading, and the position of each unit.
