---
title: agrag.ingestion.resolve.exact_resolution_groups
sidebar_label: exact_resolution_groups
---

# `agrag.ingestion.resolve.exact_resolution_groups` \{#agrag-ingestion-resolve-exact_resolution_groups}

```python
exact_resolution_groups(mentions:list[ExtractedEntity], exact_matches:dict[int, Entity]) -> list[ResolutionGroup]
```

Group mentions only when they share exact raw-entity identity.

A mention with a persisted exact match joins every other mention that
resolves to the same raw Entity. Other mentions join only when their
labels and normalized names match. Semantic matches deliberately remain
separate raw records and become resolved entities through `MATCHES` later.
