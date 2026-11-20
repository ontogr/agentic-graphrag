---
title: agrag.ingestion.resolve.candidate_source.read_candidates
sidebar_label: read_candidates
---

# `agrag.ingestion.resolve.candidate_source.read_candidates` \{#agrag-ingestion-resolve-candidate_source-read_candidates}

```python
read_candidates(source:GraphCandidateSource, mention:ExtractedEntity, *, error_policy:ErrorPolicy) -> tuple[list[tuple[Entity, float]], StageFailure | None]
```

Read the persisted candidates for one mention, or report the failure.

A failed read is not an empty result: a mention with no candidates would
become a new entity, so the caller must skip a mention whose read failed.

**Parameters:**

- **source** (<code>[GraphCandidateSource](GraphCandidateSource.md)</code>) – The candidate source to read.
- **mention** (<code>[ExtractedEntity](../../../common/data_models/extraction/ExtractedEntity.md)</code>) – The mention to find persisted candidates for.
- **error_policy** (<code>[ErrorPolicy](../../../loaders/types/ErrorPolicy.md)</code>) – RAISE propagates the failure; any other policy
  returns it as a StageFailure.

**Returns:**

- <code>list\[tuple\[[Entity](../../../common/data_models/entity/Entity-ref.md), float\]\]</code> – The `(Entity, score)` pairs and None when the read succeeded, or
- <code>[StageFailure](../../../common/data_models/stage_failure/StageFailure.md) | None</code> – an empty list and the StageFailure when it failed.

**Raises:**

- <code>Exception</code> – The read failed and `error_policy` is RAISE.
