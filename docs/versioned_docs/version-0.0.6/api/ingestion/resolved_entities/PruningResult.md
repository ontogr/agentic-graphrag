---
title: agrag.ingestion.resolved_entities.PruningResult
sidebar_label: PruningResult
---

# `agrag.ingestion.resolved_entities.PruningResult` \{#agrag-ingestion-resolved_entities-PruningResult}

Bases: <code>BaseModel</code>

Ids removed and clusters rebuilt by deletion-triggered pruning.

**Attributes:**

- [**rebuilt_entities**](#agrag-ingestion-resolved_entities-PruningResult-rebuilt_entities) (<code>list\[[ResolvedEntity](../../common/data_models/resolved_entity/ResolvedEntity.md)\]</code>) –
- [**removed_entity_ids**](#agrag-ingestion-resolved_entities-PruningResult-removed_entity_ids) (<code>list\[UUID\]</code>) –
- [**removed_resolved_entity_ids**](#agrag-ingestion-resolved_entities-PruningResult-removed_resolved_entity_ids) (<code>list\[UUID\]</code>) –

## `rebuilt_entities` \{#agrag-ingestion-resolved_entities-PruningResult-rebuilt_entities}

```python
rebuilt_entities: list[ResolvedEntity]
```

## `removed_entity_ids` \{#agrag-ingestion-resolved_entities-PruningResult-removed_entity_ids}

```python
removed_entity_ids: list[UUID]
```

## `removed_resolved_entity_ids` \{#agrag-ingestion-resolved_entities-PruningResult-removed_resolved_entity_ids}

```python
removed_resolved_entity_ids: list[UUID]
```
