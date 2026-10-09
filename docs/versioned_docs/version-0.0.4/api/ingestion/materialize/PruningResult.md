---
title: agrag.ingestion.materialize.PruningResult
sidebar_label: PruningResult
---

# `agrag.ingestion.materialize.PruningResult` \{#agrag-ingestion-materialize-PruningResult}

Bases: <code>BaseModel</code>

Ids removed and clusters rebuilt by deletion-triggered pruning.

**Attributes:**

- [**rematerialized_entities**](#agrag-ingestion-materialize-PruningResult-rematerialized_entities) (<code>list\[[ResolvedEntity](../../common/data_models/resolved_entity/ResolvedEntity.md)\]</code>) –
- [**removed_entity_ids**](#agrag-ingestion-materialize-PruningResult-removed_entity_ids) (<code>list\[UUID\]</code>) –
- [**removed_resolved_entity_ids**](#agrag-ingestion-materialize-PruningResult-removed_resolved_entity_ids) (<code>list\[UUID\]</code>) –

## `rematerialized_entities` \{#agrag-ingestion-materialize-PruningResult-rematerialized_entities}

```python
rematerialized_entities: list[ResolvedEntity]
```

## `removed_entity_ids` \{#agrag-ingestion-materialize-PruningResult-removed_entity_ids}

```python
removed_entity_ids: list[UUID]
```

## `removed_resolved_entity_ids` \{#agrag-ingestion-materialize-PruningResult-removed_resolved_entity_ids}

```python
removed_resolved_entity_ids: list[UUID]
```
