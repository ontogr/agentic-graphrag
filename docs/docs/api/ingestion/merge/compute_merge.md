---
title: agrag.ingestion.merge.compute_merge
sidebar_label: compute_merge
---

# `agrag.ingestion.merge.compute_merge` \{#agrag-ingestion-merge-compute_merge}

```python
compute_merge(*, existing_entities:list[Entity], mentions:list[ExtractedEntity], schema:GraphSchema, rules:PropertyRules | None = None, description_settings:Any | None = None, description_client:Any | None = None, job_id:UUID | str | None = None, tracer:Tracer | None = None) -> tuple[MergePlan, list[Any]]
```

Compute how existing_entities and mentions combine into one Entity.

No storage is touched. Zero existing entities produces a brand-new Entity.
One produces an updated copy folding in the mentions. Two or more picks a
canonical entity for the survivor's identity; the others contribute
property values and accepted merge-key aliases.

**Parameters:**

- **existing_entities** (<code>list\[[Entity](../../common/data_models/entity/Entity-ref.md)\]</code>) – Already-persisted entities this call reconciles.
- **mentions** (<code>list\[[ExtractedEntity](../../common/data_models/extraction/ExtractedEntity.md)\]</code>) – Fresh ExtractedEntity mentions to fold in.
- **schema** (<code>[GraphSchema](../../common/data_models/graph_schema/GraphSchema.md)</code>) – Used to look up the entity type's declared properties for the
  canonical-id schema-completeness check.
- **rules** (<code>[PropertyRules](PropertyRules.md) | None</code>) – Per-property conflict resolution. Defaults to keep_first. The
  name is always a single string: under merge_all it takes the
  canonical entity's name, or the first mention's when none exists.
- **description_settings** (<code>Any | None</code>) – LLM settings for description summarization.
- **description_client** (<code>Any | None</code>) – Injected LLM client for tests.
- **job_id** (<code>UUID | str | None</code>) – The Cutover Job this merge runs under. A brand-new entity
  derives its id from (job_id, merge_key) instead of uuid4, so
  replaying the job after a crash reproduces the same id. None
  keeps today's random-id behavior for callers outside a job.
- **tracer** (<code>Tracer | None</code>) – Passed to description summarization.

**Returns:**

- <code>tuple\[[MergePlan](MergePlan.md), list\[Any\]\]</code> – The computed MergePlan and any description-LLM failures.

**Raises:**

- <code>ValueError</code> – existing_entities and mentions are both empty, or their
  labels disagree.
