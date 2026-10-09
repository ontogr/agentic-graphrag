---
title: agrag.common.data_models.structure.version_id_for_hash
sidebar_label: version_id_for_hash
---

# `agrag.common.data_models.structure.version_id_for_hash` \{#agrag-common-data_models-structure-version_id_for_hash}

```python
version_id_for_hash(*, content_hash:str) -> str
```

Return the id of one document version from its content hash.

**Parameters:**

- **content_hash** (<code>str</code>) – The document's content hash.

**Returns:**

- <code>str</code> – The version id, which changes when the content hash changes.
