---
title: agrag.common.validation.require_valid_search_limit
sidebar_label: require_valid_search_limit
---

# `agrag.common.validation.require_valid_search_limit` \{#agrag-common-validation-require_valid_search_limit}

```python
require_valid_search_limit(limit:int) -> None
```

Check that a search/hybrid_search `limit` is usable across every backend.

Backends fail differently outside this range: Milvus raises for a
non-positive `limit` or one above `MAX_SEARCH_LIMIT` (its own
query/search result-window ceiling), while Qdrant and Weaviate may
instead return an empty or silently truncated result. Enforcing the
tightest bound uniformly means a given `limit` either works, or fails
the same way, regardless of which backend is configured.

**Parameters:**

- **limit** (<code>int</code>) – The requested maximum number of hits.

**Raises:**

- <code>ValueError</code> – `limit` is not a positive integer, or exceeds
  `MAX_SEARCH_LIMIT`.
