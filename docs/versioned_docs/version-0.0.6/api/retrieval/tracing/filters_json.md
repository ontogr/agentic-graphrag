---
title: agrag.retrieval.tracing.filters_json
sidebar_label: filters_json
---

# `agrag.retrieval.tracing.filters_json` \{#agrag-retrieval-tracing-filters_json}

```python
filters_json(filters:SearchFilters | None) -> str
```

Return the scope as JSON, an empty scope when `filters` is None.

**Parameters:**

- **filters** (<code>[SearchFilters](../filters/SearchFilters.md) | None</code>) – The scope a search or retriever ran with, or None.

**Returns:**

- <code>str</code> – The scope as JSON, never None, so a span always records it.
