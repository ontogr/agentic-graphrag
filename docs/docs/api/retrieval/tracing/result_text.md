---
title: agrag.retrieval.tracing.result_text
sidebar_label: result_text
---

# `agrag.retrieval.tracing.result_text` \{#agrag-retrieval-tracing-result_text}

```python
result_text(result:SearchResult) -> str
```

Return the text a result stands for.

Entities, resolved entities and communities give their embedding text,
chunks their text, relations `TYPE(source_id, target_id)`, and scalar
query rows JSON.

**Parameters:**

- **result** (<code>[SearchResult](../../common/data_models/search_result/SearchResult.md)</code>) – The result to render.

**Returns:**

- <code>str</code> – The text the result's item stands for.
