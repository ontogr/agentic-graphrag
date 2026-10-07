---
title: agrag.retrieval.tracing.retrieval_span
sidebar_label: retrieval_span
---

# `agrag.retrieval.tracing.retrieval_span` \{#agrag-retrieval-tracing-retrieval_span}

```python
retrieval_span(tracer:Tracer | None, name:str, *, query:str, filters:SearchFilters | None, attributes:dict[str, Any] | None = None) -> Iterator[Span]
```

Open a `RETRIEVER` span that records the query and the scope.

Use it for retriever spans and for root spans that return
`SearchResult`s. The caller calls `record_results` on the yielded span
before it exits.

**Parameters:**

- **tracer** (<code>Tracer | None</code>) – The caller's tracer, or None for a no-op tracer.
- **name** (<code>str</code>) – The span name, in the `agrag.retrieval.*` namespace.
- **query** (<code>str</code>) – The natural-language query, or the seed's text.
- **filters** (<code>[SearchFilters](../filters/SearchFilters.md) | None</code>) – The scope the wrapped call runs under, always recorded.
- **attributes** (<code>dict\[str, Any\] | None</code>) – Extra cheap attributes known before the call starts.

**Yields:**

- <code>Span</code> – The open span, for `record_results` and any later attributes.
