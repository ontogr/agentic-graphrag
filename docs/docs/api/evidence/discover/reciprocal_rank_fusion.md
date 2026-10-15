---
title: agrag.evidence.discover.reciprocal_rank_fusion
sidebar_label: reciprocal_rank_fusion
---

# `agrag.evidence.discover.reciprocal_rank_fusion` \{#agrag-evidence-discover-reciprocal_rank_fusion}

```python
reciprocal_rank_fusion(rankings:Sequence[Sequence[str]], *, constant:int = RRF_CONSTANT) -> dict[str, float]
```

Fuse ranked id lists into one score per id.

Each list adds `1 / (constant + rank)` to the score of every id it contains,
with ranks starting at 1. An id that several lists rank highly scores highest.

**Parameters:**

- **rankings** (<code>Sequence\[Sequence\[str\]\]</code>) – Lists of ids, best first. An id should appear once per list.
- **constant** (<code>int</code>) – The damping constant of the formula.

**Returns:**

- <code>dict\[str, float\]</code> – The fused score of each id that appears in any list.
