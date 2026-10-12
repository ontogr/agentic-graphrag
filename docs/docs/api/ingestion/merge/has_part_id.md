---
title: agrag.ingestion.merge.has_part_id
sidebar_label: has_part_id
---

# `agrag.ingestion.merge.has_part_id` \{#agrag-ingestion-merge-has_part_id}

```python
has_part_id(document_node_id:UUID, node_id:UUID, version_id:UUID | str) -> UUID
```

Return the id for one versioned edge from a Document node to a part.

**Parameters:**

- **document_node_id** (<code>UUID</code>) – The id of the Document graph node.
- **node_id** (<code>UUID</code>) – The id of the Chunk, Section, Table or Figure.
- **version_id** (<code>UUID | str</code>) – The identifier for this document version.

**Returns:**

- <code>UUID</code> – The edge id. Each document version gets a separate relationship id.
