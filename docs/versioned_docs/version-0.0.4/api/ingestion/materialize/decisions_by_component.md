---
title: agrag.ingestion.materialize.decisions_by_component
sidebar_label: decisions_by_component
---

# `agrag.ingestion.materialize.decisions_by_component` \{#agrag-ingestion-materialize-decisions_by_component}

```python
decisions_by_component(matches:list[ResolvedMatch], mention_to_entity:dict[int, UUID]) -> list[list[MatchDecision]]
```

Map resolution evidence to raw ids and group it by connected component.
