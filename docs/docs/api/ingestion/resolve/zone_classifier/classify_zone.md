---
title: agrag.ingestion.resolve.zone_classifier.classify_zone
sidebar_label: classify_zone
---

# `agrag.ingestion.resolve.zone_classifier.classify_zone` \{#agrag-ingestion-resolve-zone_classifier-classify_zone}

```python
classify_zone(fuzzy_score:float, embedding_similarity:float | None) -> str
```

Assign a candidate pair to a resolution zone.

A near-identical fuzzy score merges without consulting the embedding.
Otherwise the embedding similarity decides: at or above the hard-merge
threshold the pair merges, inside the discard-to-hard-merge band it
needs LLM review, and below the discard threshold it is dropped. A
missing embedding with a below-fast-path fuzzy score also discards,
since no signal supports a merge.

**Parameters:**

- **fuzzy_score** (<code>float</code>) – Token-sort-ratio similarity in `[0, 1]`.
- **embedding_similarity** (<code>float | None</code>) – Cosine similarity in `[-1, 1]`, or `None`
  when no embedding is available.

**Returns:**

- <code>str</code> – `"hard_merge"`, `"ambiguous"`, or `"discard"`.
