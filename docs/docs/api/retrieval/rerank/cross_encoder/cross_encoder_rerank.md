---
title: agrag.retrieval.rerank.cross_encoder.cross_encoder_rerank
sidebar_label: cross_encoder_rerank
---

# `agrag.retrieval.rerank.cross_encoder.cross_encoder_rerank` \{#agrag-retrieval-rerank-cross_encoder-cross_encoder_rerank}

```python
cross_encoder_rerank(query:str, results:list[SearchResult], *, model:str = 'cross-encoder/ms-marco-MiniLM-L-6-v2', min_score:float | None = None, tracer:Tracer | None = None) -> list[SearchResult]
```

Rerank results using a cross-encoder model.

Requires the `embed-local` extra (sentence-transformers). Scores
(query, text) pairs and reorders by relevance. Drops results scoring
below min_score when set. The model is cached per name (see
\_load_cross_encoder), and the blocking predict() call runs via
asyncio.to_thread so a larger configured model cannot stall the event
loop for other concurrent search() calls. Concurrent first loads of the
same model share one in-flight construction behind a per-model lock, so
only one instance (and one download) occurs.

Without the extra, the results are returned unchanged: the span records
the ImportError and sets `agrag.skipped`, and its status stays UNSET.

**Parameters:**

- **query** (<code>str</code>) – The natural-language query text.
- **results** (<code>list\[[SearchResult](../../../common/data_models/search_result/SearchResult.md)\]</code>) – The fused results to rerank.
- **model** (<code>str</code>) – The sentence-transformers CrossEncoder model name/path.
  Callers pass RetrievalSettings.cross_encoder_model.
- **min_score** (<code>float | None</code>) – Optional minimum score threshold. Results below this
  are dropped.
- **tracer** (<code>Tracer | None</code>) – Opens the rerank spans. None opens no recorded span.

**Returns:**

- <code>list\[[SearchResult](../../../common/data_models/search_result/SearchResult.md)\]</code> – Results reranked by cross-encoder score, descending.
