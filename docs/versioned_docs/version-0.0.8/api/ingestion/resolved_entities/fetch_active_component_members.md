---
title: agrag.ingestion.resolved_entities.fetch_active_component_members
sidebar_label: fetch_active_component_members
---

# `agrag.ingestion.resolved_entities.fetch_active_component_members` \{#agrag-ingestion-resolved_entities-fetch_active_component_members}

```python
fetch_active_component_members(transaction:GraphStoreTransaction, seed_ids:Sequence[str], job_id:str | None) -> list[dict[str, Any]]
```

Return the entities joined to each seed by active matches, seed included.

The component grows one match at a time, so the work follows the size of
the component and not the number of paths through it.

**Parameters:**

- **transaction** (<code>[GraphStoreTransaction](../../graphdb/base/GraphStoreTransaction.md)</code>) – The transaction to read in.
- **seed_ids** (<code>Sequence\[str\]</code>) – Ids of the entities to start from.
- **job_id** (<code>str | None</code>) – The in-flight job's id, or None outside a job.

**Returns:**

- <code>list\[dict\[str, Any\]\]</code> – One `{"seed_id", "member"}` row per seed and member, where `member`
- <code>list\[dict\[str, Any\]\]</code> – is the node's property dict. A seed that is not visible has no rows.
