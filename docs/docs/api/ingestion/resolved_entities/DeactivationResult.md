---
title: agrag.ingestion.resolved_entities.DeactivationResult
sidebar_label: DeactivationResult
---

# `agrag.ingestion.resolved_entities.DeactivationResult` \{#agrag-ingestion-resolved_entities-DeactivationResult}

Bases: <code>BaseModel</code>

Resolved entities created after a match correction and stale ids removed.

**Attributes:**

- [**removed_entity_ids**](#agrag-ingestion-resolved_entities-DeactivationResult-removed_entity_ids) (<code>list\[UUID\]</code>) –
- [**resolved_entities**](#agrag-ingestion-resolved_entities-DeactivationResult-resolved_entities) (<code>list\[[ResolvedEntity](../../common/data_models/resolved_entity/ResolvedEntity.md)\]</code>) –

## `removed_entity_ids` \{#agrag-ingestion-resolved_entities-DeactivationResult-removed_entity_ids}

```python
removed_entity_ids: list[UUID]
```

## `resolved_entities` \{#agrag-ingestion-resolved_entities-DeactivationResult-resolved_entities}

```python
resolved_entities: list[ResolvedEntity]
```
