---
title: agrag.common.data_models.structure.common_ancestor
sidebar_label: common_ancestor
---

# `agrag.common.data_models.structure.common_ancestor` \{#agrag-common-data_models-structure-common_ancestor}

```python
common_ancestor(sections:list[DocumentSection], indexes:list[int]) -> int | None
```

Return the lowest section that contains all the given sections.

**Parameters:**

- **sections** (<code>list\[[DocumentSection](../document/DocumentSection.md)\]</code>) – The sections of a document.
- **indexes** (<code>list\[int\]</code>) – The indexes of the sections to contain. A section contains itself.

**Returns:**

- <code>int | None</code> – The index of the section, or `None` when only the document contains them.
