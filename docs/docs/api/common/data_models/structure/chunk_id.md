---
title: agrag.common.data_models.structure.chunk_id
sidebar_label: chunk_id
---

# `agrag.common.data_models.structure.chunk_id` \{#agrag-common-data_models-structure-chunk_id}

```python
chunk_id(document_id:UUID, version:str, chunker_hash:str, index:int) -> UUID
```

Return the id of a chunk.

**Parameters:**

- **document_id** (<code>UUID</code>) – The id of the Document node.
- **version** (<code>str</code>) – The document version from `version_id`.
- **chunker_hash** (<code>str</code>) – The fingerprint of the chunker settings.
- **index** (<code>int</code>) – The position of the chunk in the document.

**Returns:**

- <code>UUID</code> – The id. It changes with the version and with the chunker settings.
