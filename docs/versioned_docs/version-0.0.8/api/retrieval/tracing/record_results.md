---
title: agrag.retrieval.tracing.record_results
sidebar_label: record_results
---

# `agrag.retrieval.tracing.record_results` \{#agrag-retrieval-tracing-record_results}

```python
record_results(span:Span, results:Sequence[SearchResult]) -> None
```

Write the results onto `span`.

Full lists go in array attributes, one attribute per array, so the SDK's
per-span attribute limit does not cut a long list. The first
`MAX_DOCUMENT_ATTRIBUTES` results also use the OpenInference
`retrieval.documents.N.*` names, which viewers draw as a retrieval panel.

**Parameters:**

- **span** (<code>Span</code>) – The span that returned `results`. No-op when it is not
  recording.
- **results** (<code>Sequence\[[SearchResult](../../common/data_models/search_result/SearchResult.md)\]</code>) – The results the span's wrapped call returned, in order.
