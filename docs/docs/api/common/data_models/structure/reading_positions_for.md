---
title: agrag.common.data_models.structure.reading_positions_for
sidebar_label: reading_positions_for
---

# `agrag.common.data_models.structure.reading_positions_for` \{#agrag-common-data_models-structure-reading_positions_for}

```python
reading_positions_for(sections:list[DocumentSection]) -> tuple[list[int], list[list[int]]]
```

Number every heading and unit of a section list in reading order.

**Parameters:**

- **sections** (<code>list\[[DocumentSection](../document/DocumentSection.md)\]</code>) – The sections of a document, in reading order.

**Returns:**

- <code>tuple\[list\[int\], list\[list\[int\]\]\]</code> – The position of each section heading, and the position of each unit.
