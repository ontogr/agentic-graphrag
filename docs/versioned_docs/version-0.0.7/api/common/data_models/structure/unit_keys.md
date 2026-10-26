---
title: agrag.common.data_models.structure.unit_keys
sidebar_label: unit_keys
---

# `agrag.common.data_models.structure.unit_keys` \{#agrag-common-data_models-structure-unit_keys}

```python
unit_keys(document:Document, keys:list[UUID]) -> dict[tuple[int, int], UUID]
```

Return a stable key for each table and figure.

**Parameters:**

- **document** (<code>[Document](../document/Document-ref.md)</code>) – The document.
- **keys** (<code>list\[UUID\]</code>) – The section keys from `section_keys`.

**Returns:**

- <code>dict\[tuple\[int, int\], UUID\]</code> – The keys, by section index and unit index.
