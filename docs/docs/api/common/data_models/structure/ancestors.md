---
title: agrag.common.data_models.structure.ancestors
sidebar_label: ancestors
---

# `agrag.common.data_models.structure.ancestors` \{#agrag-common-data_models-structure-ancestors}

```python
ancestors(sections:list[DocumentSection], index:int) -> list[int]
```

Return the index of a section and of each section above it.

**Parameters:**

- **sections** (<code>list\[[DocumentSection](../document/DocumentSection.md)\]</code>) – The sections of a document.
- **index** (<code>int</code>) – The index of the section.

**Returns:**

- <code>list\[int\]</code> – The indexes from the outermost ancestor down to the section itself.
