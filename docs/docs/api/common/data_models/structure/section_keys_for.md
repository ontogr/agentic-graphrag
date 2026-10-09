---
title: agrag.common.data_models.structure.section_keys_for
sidebar_label: section_keys_for
---

# `agrag.common.data_models.structure.section_keys_for` \{#agrag-common-data_models-structure-section_keys_for}

```python
section_keys_for(sections:list[DocumentSection], document_key:str) -> list[UUID]
```

Return one stable key for each section.

A key stays the same across versions while the heading path of the
section and its place among sections with the same path stay the same.

**Parameters:**

- **sections** (<code>list\[[DocumentSection](../document/DocumentSection.md)\]</code>) – The sections of a document, in reading order.
- **document_key** (<code>str</code>) – The stable key of the document.

**Returns:**

- <code>list\[UUID\]</code> – The keys, in the order of `sections`.
