---
title: agrag.ingestion.resolve.candidate_source.build_relation_neighbors
sidebar_label: build_relation_neighbors
---

# `agrag.ingestion.resolve.candidate_source.build_relation_neighbors` \{#agrag-ingestion-resolve-candidate_source-build_relation_neighbors}

```python
build_relation_neighbors(entities:list[ExtractedEntity], relations:Sequence[ExtractedRelation], *, max_neighbors:int = MAX_NEIGHBORS_PER_ENTITY) -> dict[int, list[str]]
```

Build LLMVerify neighbor context from one batch's extracted relations.

**Parameters:**

- **entities** (<code>list\[[ExtractedEntity](../../../common/data_models/extraction/ExtractedEntity.md)\]</code>) – The batch's mentions, indexed as `relations` references
  them.
- **relations** (<code>Sequence\[[ExtractedRelation](../../../common/data_models/extraction/ExtractedRelation.md)\]</code>) – Relation mentions from the same extraction batch.
- **max_neighbors** (<code>int</code>) – Maximum neighbor strings kept per entity index.

**Returns:**

- <code>dict\[int, list\[str\]\]</code> – Entity index to a list of `"{relation_label} {other_entity_text}"`
- <code>dict\[int, list\[str\]\]</code> – strings, each direction of a relation contributing one entry to
- <code>dict\[int, list\[str\]\]</code> – both endpoints, capped at `max_neighbors` per index. An index with no
- <code>dict\[int, list\[str\]\]</code> – relation names has no key at all.
