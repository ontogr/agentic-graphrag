---
title: agrag.evidence.rerank.reranker_from_settings
sidebar_label: reranker_from_settings
---

# `agrag.evidence.rerank.reranker_from_settings` \{#agrag-evidence-rerank-reranker_from_settings}

```python
reranker_from_settings(settings:RetrievalSettings) -> CrossEncoderReranker | None
```

Build the reranker the retrieval settings configure, or `None`.

Never loads the model; loading happens on the first rerank call or an
explicit `warm_up`.

**Parameters:**

- **settings** (<code>[RetrievalSettings](../../retrieval/settings/RetrievalSettings.md)</code>) – The retrieval settings to read.

**Returns:**

- <code>[CrossEncoderReranker](CrossEncoderReranker.md) | None</code> – A `CrossEncoderReranker` when rerank is enabled and
- <code>[CrossEncoderReranker](CrossEncoderReranker.md) | None</code> – sentence-transformers is installed. `None` when rerank is
- <code>[CrossEncoderReranker](CrossEncoderReranker.md) | None</code> – disabled, or when it is enabled but the `embed-local` extra is
- <code>[CrossEncoderReranker](CrossEncoderReranker.md) | None</code> – missing (one warning is logged; hybrid search runs without rerank).
