---
title: agrag.ingestion.merge.has_child_id
sidebar_label: has_child_id
---

# `agrag.ingestion.merge.has_child_id` \{#agrag-ingestion-merge-has_child_id}

```python
has_child_id(parent_id:UUID, child_id:UUID, version_id:UUID | str) -> UUID
```

Return the id for one versioned parent -[:HAS_CHILD]-> child edge.

**Parameters:**

- **parent_id** (<code>UUID</code>) – The id of the parent node (document, section, or table).
- **child_id** (<code>UUID</code>) – The id of the child node.
- **version_id** (<code>UUID | str</code>) – The identifier for this document version.

**Returns:**

- <code>UUID</code> – The edge id. Each document version gets separate edge ids, so an
- <code>UUID</code> – identical re-ingest rebuilds the same ids and converges while a new
- <code>UUID</code> – version shares no edge with the one it supersedes.
