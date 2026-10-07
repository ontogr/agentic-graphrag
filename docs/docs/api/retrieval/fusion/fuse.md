---
title: agrag.retrieval.fusion.fuse
sidebar_label: fuse
---

# `agrag.retrieval.fusion.fuse` \{#agrag-retrieval-fusion-fuse}

```python
fuse(results_by_method:dict[str, list[SearchResult]], *, rrf_k:int = 60, tracer:Tracer | None = None) -> list[SearchResult]
```

Combine every method's ranked results into one deduplicated list.

Runs unconditionally, even for a single method, so a rerank pass
never sees duplicates. Uses Reciprocal Rank Fusion. An item's
fused score is the sum of 1 / (rrf_k + rank) across every method
that returned it.

Each method contributes at most one vote per item, scored at the
item's best (lowest) rank within that method. A multi-label
entity that surfaces in two positions of one method's output only
adds one vote from that method, so duplicate hits from a single
retriever cannot unfairly promote an item over a single best hit
from another method.

Deduplication uses SearchResult.identity_key, which is (type, id).
Fusion does not re-resolve identity. It deduplicates on the ids each
SearchResult carries.

**Parameters:**

- **results_by_method** (<code>dict\[str, list\[[SearchResult](../../common/data_models/search_result/SearchResult.md)\]\]</code>) – Each method's own ranked output, keyed by
  method name.
- **rrf_k** (<code>int</code>) – The RRF constant; higher values flatten the influence
  of rank position.
- **tracer** (<code>Tracer | None</code>) – Opens the fusion span. None opens no recorded span.

**Returns:**

- <code>list\[[SearchResult](../../common/data_models/search_result/SearchResult.md)\]</code> – One list, ranked by fused score descending, one entry per
- <code>list\[[SearchResult](../../common/data_models/search_result/SearchResult.md)\]</code> – distinct identity_key.
