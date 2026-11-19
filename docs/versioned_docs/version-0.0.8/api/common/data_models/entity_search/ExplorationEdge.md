---
title: agrag.common.data_models.entity_search.ExplorationEdge
sidebar_label: ExplorationEdge
---

# `agrag.common.data_models.entity_search.ExplorationEdge` \{#agrag-common-data_models-entity_search-ExplorationEdge}

Bases: <code>BaseModel</code>

One relation between two entities found by exploration.

**Attributes:**

- [**source_id**](#agrag-common-data_models-entity_search-ExplorationEdge-source_id) (<code>str</code>) – The id of the entity at the start of the stored relation.
- [**target_id**](#agrag-common-data_models-entity_search-ExplorationEdge-target_id) (<code>str</code>) – The id of the entity at the end of the stored relation.
- [**relation_type**](#agrag-common-data_models-entity_search-ExplorationEdge-relation_type) (<code>str</code>) – The relation type.
- [**kind**](#agrag-common-data_models-entity_search-ExplorationEdge-kind) (<code>[EdgeKind](EdgeKind.md)</code>) – Whether the edge is an assertion or a path.
- [**evidence**](#agrag-common-data_models-entity_search-ExplorationEdge-evidence) (<code>list\[[SupportingPassage](SupportingPassage.md)\]</code>) – The visible supporting passages. Empty for a path.

## `evidence` \{#agrag-common-data_models-entity_search-ExplorationEdge-evidence}

```python
evidence: list[SupportingPassage] = Field(default_factory=list)
```

## `kind` \{#agrag-common-data_models-entity_search-ExplorationEdge-kind}

```python
kind: EdgeKind
```

## `relation_type` \{#agrag-common-data_models-entity_search-ExplorationEdge-relation_type}

```python
relation_type: str
```

## `source_id` \{#agrag-common-data_models-entity_search-ExplorationEdge-source_id}

```python
source_id: str
```

## `target_id` \{#agrag-common-data_models-entity_search-ExplorationEdge-target_id}

```python
target_id: str
```
