---
title: agrag.ingestion.resolve.candidate_source.persisted_candidate_indices
sidebar_label: persisted_candidate_indices
---

# `agrag.ingestion.resolve.candidate_source.persisted_candidate_indices` \{#agrag-ingestion-resolve-candidate_source-persisted_candidate_indices}

```python
persisted_candidate_indices(mentions:list[ExtractedEntity], entities:list[Entity], *, source:GraphCandidateSource, fallback_limit:int = 128) -> tuple[dict[int, list[int]], dict[tuple[int, int], float]]
```

Return ANN candidate indices, with a bounded exhaustive fallback.

The fallback only applies when no indexed candidates are available. It
keeps first-time and small-graph consolidation deterministic without
returning to an unbounded pairwise scan for established graphs.

**Returns:**

- <code>dict\[int, list\[int\]\]</code> – Mention index to its candidate entity indices, plus each compared
- <code>dict\[tuple\[int, int\], float\]</code> – pair's real embedding cosine similarity keyed by `(min, max)`
- <code>tuple\[dict\[int, list\[int\]\], dict\[tuple\[int, int\], float\]\]</code> – index order (matching how `Resolver.resolve` builds its own pair
- <code>tuple\[dict\[int, list\[int\]\], dict\[tuple\[int, int\], float\]\]</code> – keys). The exhaustive-fallback branch reports no scores, so its
- <code>tuple\[dict\[int, list\[int\]\], dict\[tuple\[int, int\], float\]\]</code> – similarity map is empty.
