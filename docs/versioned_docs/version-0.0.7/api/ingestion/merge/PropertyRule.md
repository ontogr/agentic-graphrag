---
title: agrag.ingestion.merge.PropertyRule
sidebar_label: PropertyRule
---

# `agrag.ingestion.merge.PropertyRule` \{#agrag-ingestion-merge-PropertyRule}

```python
PropertyRule = Callable[[list[object]], object]
```

Per-property conflict resolver.

Takes every candidate value for one property, in encounter order, already
filtered to exclude None, and returns the resolved value.
