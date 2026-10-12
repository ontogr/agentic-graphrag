---
title: agrag.ingestion.resolve.zone_classifier.select_llm_pairs
sidebar_label: select_llm_pairs
---

# `agrag.ingestion.resolve.zone_classifier.select_llm_pairs` \{#agrag-ingestion-resolve-zone_classifier-select_llm_pairs}

```python
select_llm_pairs(candidates:list[tuple[int, int, float]], *, max_pairs:int = MAX_LLM_PAIRS) -> list[tuple[int, int]]
```

Rank ambiguous candidates for LLM review and keep the first `max_pairs`.

The order is similarity, highest first. Pairs with equal similarity keep the
lower `(left_index, right_index)` first, so the same input always yields
the same pairs. The pairs this drops are the least similar, and the caller
must report them as undecided.

**Parameters:**

- **candidates** (<code>list\[tuple\[int, int, float\]\]</code>) – `(left_index, right_index, similarity)` triples.
- **max_pairs** (<code>int</code>) – Maximum pairs to return.

**Returns:**

- <code>list\[tuple\[int, int\]\]</code> – Index pairs in the order above, at most `max_pairs` of them.
