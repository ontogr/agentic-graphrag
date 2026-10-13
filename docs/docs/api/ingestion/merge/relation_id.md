---
title: agrag.ingestion.merge.relation_id
sidebar_label: relation_id
---

# `agrag.ingestion.merge.relation_id` \{#agrag-ingestion-merge-relation_id}

```python
relation_id(source_id:UUID, target_id:UUID, rel_type:str) -> UUID
```

Return the committed id for a domain relationship triple.

This is the identity a relation has once committed. While a Cutover Job is
pending, the job creates the relation under `pending_relation_id` and the
commit folds it into this id.

**Parameters:**

- **source_id** (<code>UUID</code>) – The relationship's source Entity id.
- **target_id** (<code>UUID</code>) – The relationship's target Entity id.
- **rel_type** (<code>str</code>) – The relationship's type.

**Returns:**

- <code>UUID</code> – The relationship id. Same triple always returns the same id.
