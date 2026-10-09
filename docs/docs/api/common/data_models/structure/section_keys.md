---
title: agrag.common.data_models.structure.section_keys
sidebar_label: section_keys
---

# `agrag.common.data_models.structure.section_keys` \{#agrag-common-data_models-structure-section_keys}

```python
section_keys(document:Document) -> list[UUID]
```

Return one stable key for each section.

Thin wrapper over `section_keys_for`.

A key stays the same across versions while the heading path of the section and
its place among sections with the same path stay the same.

**Parameters:**

- **document** (<code>[Document](../document/Document-ref.md)</code>) – The document.

**Returns:**

- <code>list\[UUID\]</code> – The keys, in the order of `document.sections`.
