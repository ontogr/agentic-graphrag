---
title: agrag.retrieval.methods.traversal.extract_entity_ids
sidebar_label: extract_entity_ids
---

# `agrag.retrieval.methods.traversal.extract_entity_ids` \{#agrag-retrieval-methods-traversal-extract_entity_ids}

```python
extract_entity_ids(results:list[SearchResult]) -> list[UUID]
```

Return raw entity ids from results, preserving order.

Used for BFS seeds and node-distance reranking. Keeps the
first-seen id of each entity so the fusion ranking is respected. A
ResolvedEntity contributes its raw member ids, since graph
traversal and distance run over raw entity nodes: a resolved
entity's own id names no `_AgragNode` an entity traversal can
start from, so seeding with it would silently match nothing.
Chunks and other non-entity result items are skipped.

**Parameters:**

- **results** (<code>list\[[SearchResult](../../../common/data_models/search_result/SearchResult.md)\]</code>) – The result list to read entity ids from.

**Returns:**

- <code>list\[UUID\]</code> – Each entity id once, in first-seen order.
