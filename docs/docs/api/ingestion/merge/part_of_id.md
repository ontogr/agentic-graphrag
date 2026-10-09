---
title: agrag.ingestion.merge.part_of_id
sidebar_label: part_of_id
---

# `agrag.ingestion.merge.part_of_id` \{#agrag-ingestion-merge-part_of_id}

```python
part_of_id(document_node_id:UUID, node_id:UUID, version_id:UUID | str) -> UUID
```

Return the id for one versioned Document -[:PART_OF]-> node edge.

**Parameters:**

- **document_node_id** (<code>UUID</code>) – The id of the Document graph node.
- **node_id** (<code>UUID</code>) – The id of the Chunk, Section, Table or Figure.
- **version_id** (<code>UUID | str</code>) – The identifier for this document version.

**Returns:**

- <code>UUID</code> – The edge id. Each document version gets a separate relationship id.
