---
title: agrag.ingestion.resolve.persisted_candidate_indices
sidebar_label: persisted_candidate_indices
---

# `agrag.ingestion.resolve.persisted_candidate_indices` \{#agrag-ingestion-resolve-persisted_candidate_indices}

```python
persisted_candidate_indices(mentions:list[ExtractedEntity], entities:list[Entity], *, source:GraphCandidateSource, error_policy:ErrorPolicy, fallback_limit:int = 128) -> tuple[dict[int, list[int]], dict[tuple[int, int], float], list[StageFailure]]
```

Return ANN candidate indices, with a bounded exhaustive fallback.

The fallback only applies when no indexed candidates are available. It
keeps first-time and small-graph consolidation deterministic without
returning to an unbounded pairwise scan for established graphs.

**Returns:**

- <code>dict\[int, list\[int\]\]</code> – Mention index to its candidate entity indices, plus each compared
- <code>dict\[tuple\[int, int\], float\]</code> – pair's real embedding cosine similarity keyed by `(min, max)`
- <code>list\[[StageFailure](../../common/data_models/stage_failure/StageFailure.md)\]</code> – index order (matching how `Resolver.resolve` builds its own pair
- <code>tuple\[dict\[int, list\[int\]\], dict\[tuple\[int, int\], float\], list\[[StageFailure](../../common/data_models/stage_failure/StageFailure.md)\]\]</code> – keys), plus one StageFailure per mention whose candidate read
- <code>tuple\[dict\[int, list\[int\]\], dict\[tuple\[int, int\], float\], list\[[StageFailure](../../common/data_models/stage_failure/StageFailure.md)\]\]</code> – failed. The exhaustive-fallback branch reports no scores, so its
- <code>tuple\[dict\[int, list\[int\]\], dict\[tuple\[int, int\], float\], list\[[StageFailure](../../common/data_models/stage_failure/StageFailure.md)\]\]</code> – similarity map is empty. A mention whose read failed neither starts
- <code>tuple\[dict\[int, list\[int\]\], dict\[tuple\[int, int\], float\], list\[[StageFailure](../../common/data_models/stage_failure/StageFailure.md)\]\]</code> – nor joins a comparison, so it is not resolved in this call.

**Raises:**

- <code>Exception</code> – A candidate read failed and `error_policy` is RAISE.
