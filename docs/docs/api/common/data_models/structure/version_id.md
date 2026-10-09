---
title: agrag.common.data_models.structure.version_id
sidebar_label: version_id
---

# `agrag.common.data_models.structure.version_id` \{#agrag-common-data_models-structure-version_id}

```python
version_id(document:Document) -> str
```

Return the id of one version of a document, as `PART_OF` edges use it.

Thin wrapper over `version_id_for_hash`.

**Parameters:**

- **document** (<code>[Document](../document/Document-ref.md)</code>) – The document.

**Returns:**

- <code>str</code> – The id, which changes when the content hash changes.
