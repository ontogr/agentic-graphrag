---
title: agrag.retrieval.community_context.expand_with_communities
sidebar_label: expand_with_communities
---

# `agrag.retrieval.community_context.expand_with_communities` \{#agrag-retrieval-community_context-expand_with_communities}

```python
expand_with_communities(fused:list[SearchResult], seed_ids:list[UUID], *, graph_store:GraphStore, top_k:int, filters:SearchFilters | None, rrf_k:int, tracer:Tracer | None = None) -> list[SearchResult]
```

Fuse community reports overlapping seed entities into a result list.

A convenience over :func:`community_context`: looks up the communities
that overlap `seed_ids` and fuses whatever comes back into `fused`
under a `"community"` key, so callers that already have a fused
result list do not repeat the fetch-then-fuse pattern (or the
error handling below).

A community lookup that raises is recorded on the expansion span and
swallowed rather than propagating: community reports are enrichment on
top of results that already exist, so a community-store failure must
not discard them.

**Parameters:**

- **fused** (<code>list\[[SearchResult](../../common/data_models/search_result/SearchResult.md)\]</code>) – The already-fused results to enrich. Returned unchanged
  when no community overlaps the seeds.
- **seed_ids** (<code>list\[UUID\]</code>) – The entity ids to look for overlapping communities.
- **graph_store** (<code>[GraphStore](../../graphdb/base/GraphStore.md)</code>) – Where the overlap lookup runs.
- **top_k** (<code>int</code>) – The maximum number of communities to add.
- **filters** (<code>[SearchFilters](../filters/SearchFilters.md) | None</code>) – Applied to the candidate community node; see
  :func:`community_context` for what a scoped filter does and
  does not match. Community nodes carry no entity label and no
  document scope of their own, so a document- or
  property-scoped caller gets no community enrichment at all --
  consistent with a plain search, not an error.
- **rrf_k** (<code>int</code>) – The reciprocal-rank-fusion constant, from
  `RetrievalSettings.rrf_k`.
- **tracer** (<code>Tracer | None</code>) – Opens the expansion spans. None opens no recorded span.

**Returns:**

- <code>list\[[SearchResult](../../common/data_models/search_result/SearchResult.md)\]</code> – `fused` with the overlapping communities fused in, or `fused`
- <code>list\[[SearchResult](../../common/data_models/search_result/SearchResult.md)\]</code> – itself when there were none.
