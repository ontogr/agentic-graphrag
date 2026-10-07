---
title: agrag.ingestion.resolve.find_exact_matches
sidebar_label: find_exact_matches
---

# `agrag.ingestion.resolve.find_exact_matches` \{#agrag-ingestion-resolve-find_exact_matches}

```python
find_exact_matches(mentions:list[ExtractedEntity], *, graph_store:GraphStore, job_id:UUID | str | None = None) -> dict[int, Entity]
```

Return each mention index's matching persisted Entity, if it has one.

One batched read per distinct label present in mentions. A row is
mapped back to its mention(s) by the merge_key the row's alias was
matched on -- returned alongside the node by fetch_by_merge_keys_query
-- rather than by re-deriving a key from the resolved entity's current
name: an accepted alias can name an entity by something other than its
current canonical name (see upsert_merge_alias_query), so re-deriving
would silently fail to map those mentions back. Rows without a returned
merge_key (plain mocks) fall back to the resolved entity's own
merge_key.

**Parameters:**

- **mentions** (<code>list\[[ExtractedEntity](../../common/data_models/extraction/ExtractedEntity.md)\]</code>) – The entity mentions to look up.
- **graph_store** (<code>[GraphStore](../../graphdb/base/GraphStore.md)</code>) – Where the lookup runs.
- **job_id** (<code>UUID | str | None</code>) – The in-flight Cutover Job's id, so the alias/node guards
  admit this job's own pending writes while excluding every
  other in-flight job's. None reads committed-only.

**Returns:**

- <code>dict\[int, [Entity](../../common/data_models/entity/Entity-ref.md)\]</code> – A map from mention index to its matching Entity.
