---
title: agrag.ingestion.resolve.zone_classifier.precluster_ambiguous
sidebar_label: precluster_ambiguous
---

# `agrag.ingestion.resolve.zone_classifier.precluster_ambiguous` \{#agrag-ingestion-resolve-zone_classifier-precluster_ambiguous}

```python
precluster_ambiguous(ids:list[UUID], similarities:Mapping[tuple[int, int], float], *, hard_merge_threshold:float = HARD_MERGE_THRESHOLD) -> list[list[UUID]]
```

Find tight ambiguous sub-clusters that can merge without LLM review.

Runs average-linkage clustering cut at `1 - HARD_MERGE_THRESHOLD` so
only groups whose mean pairwise distance sits inside the hard-merge
zone come back. Pairs absent from `similarities` count as maximally
distant and never join a group.

**Parameters:**

- **ids** (<code>list\[UUID\]</code>) – Candidate entity identifiers.
- **similarities** (<code>Mapping\[tuple\[int, int\], float\]</code>) – Cosine similarity keyed by `(left, right)` index
  into `ids`, symmetric entries optional.
- **hard_merge_threshold** (<code>float</code>) – Similarity required for an automatic merge.

**Returns:**

- <code>list\[list\[UUID\]\]</code> – Only multi-member groups; singletons need LLM review or discard.
