---
title: agrag.ingestion.merge.relation_id
sidebar_label: relation_id
---

# `agrag.ingestion.merge.relation_id` \{#agrag-ingestion-merge-relation_id}

```python
relation_id(source_id:UUID, target_id:UUID, rel_type:str) -> UUID
```

Return the deterministic id for a domain relationship triple.

Two concurrent `add()` calls resolving the same `(source_id, target_id, rel_type)` triple can both miss the existing-relation lookup
and each try to create it. Since this id depends only on the triple, both
writers compute the same one, so `upsert_relation_query`'s `MERGE`
converges to a single edge instead of two parallel ones with unrelated
random ids. Mirrors `mentioned_in_id`.

**Parameters:**

- **source_id** (<code>UUID</code>) – The relationship's source Entity id.
- **target_id** (<code>UUID</code>) – The relationship's target Entity id.
- **rel_type** (<code>str</code>) – The relationship's type.

**Returns:**

- <code>UUID</code> – The relationship id. Same triple always returns the same id.
