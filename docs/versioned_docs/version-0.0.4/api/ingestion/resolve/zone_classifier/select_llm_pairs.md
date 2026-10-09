---
title: agrag.ingestion.resolve.zone_classifier.select_llm_pairs
sidebar_label: select_llm_pairs
---

# `agrag.ingestion.resolve.zone_classifier.select_llm_pairs` \{#agrag-ingestion-resolve-zone_classifier-select_llm_pairs}

```python
select_llm_pairs(candidates:list[tuple[int, int, float]], *, max_pairs:int = MAX_LLM_PAIRS) -> list[tuple[int, int]]
```

Rank ambiguous candidates for LLM review, most similar first.

**Parameters:**

- **candidates** (<code>list\[tuple\[int, int, float\]\]</code>) – `(left_index, right_index, similarity)` triples.
- **max_pairs** (<code>int</code>) – Maximum pairs to return.

**Returns:**

- <code>list\[tuple\[int, int\]\]</code> – Index pairs ordered by similarity descending, capped at
- <code>list\[tuple\[int, int\]\]</code> – `max_pairs`.
