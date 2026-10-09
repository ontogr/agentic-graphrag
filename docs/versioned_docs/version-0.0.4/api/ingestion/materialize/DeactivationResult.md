---
title: agrag.ingestion.materialize.DeactivationResult
sidebar_label: DeactivationResult
---

# `agrag.ingestion.materialize.DeactivationResult` \{#agrag-ingestion-materialize-DeactivationResult}

Bases: <code>BaseModel</code>

Materializations created after a match correction and stale ids removed.

**Attributes:**

- [**removed_entity_ids**](#agrag-ingestion-materialize-DeactivationResult-removed_entity_ids) (<code>list\[UUID\]</code>) –
- [**resolved_entities**](#agrag-ingestion-materialize-DeactivationResult-resolved_entities) (<code>list\[[ResolvedEntity](../../common/data_models/resolved_entity/ResolvedEntity.md)\]</code>) –

## `removed_entity_ids` \{#agrag-ingestion-materialize-DeactivationResult-removed_entity_ids}

```python
removed_entity_ids: list[UUID]
```

## `resolved_entities` \{#agrag-ingestion-materialize-DeactivationResult-resolved_entities}

```python
resolved_entities: list[ResolvedEntity]
```
