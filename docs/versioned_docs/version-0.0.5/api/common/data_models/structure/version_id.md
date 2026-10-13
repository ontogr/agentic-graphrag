---
title: agrag.common.data_models.structure.version_id
sidebar_label: version_id
---

# `agrag.common.data_models.structure.version_id` \{#agrag-common-data_models-structure-version_id}

```python
version_id(document:Document) -> str
```

Return the id of one version of a document, as `HAS_PART` edges use it.

A version is one content together with the schema structure that ran
against it. A new structure makes new sections and chunks. A change of
descriptions or extraction settings keeps the version, so its chunks stay.

**Parameters:**

- **document** (<code>[Document](../document/Document-ref.md)</code>) – The document.

**Returns:**

- <code>str</code> – The id, which changes when the content hash or the schema fingerprint
- <code>str</code> – changes.
