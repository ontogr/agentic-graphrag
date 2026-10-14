---
title: agrag.common.data_models.entity_search.ExplorationResult
sidebar_label: ExplorationResult
---

# `agrag.common.data_models.entity_search.ExplorationResult` \{#agrag-common-data_models-entity_search-ExplorationResult}

Bases: <code>BaseModel</code>

The result of one exploration call.

**Attributes:**

- [**status**](#agrag-common-data_models-entity_search-ExplorationResult-status) (<code>[ExplorationStatus](ExplorationStatus.md)</code>) – The overall outcome.
- [**nodes**](#agrag-common-data_models-entity_search-ExplorationResult-nodes) (<code>list\[[ExplorationNode](ExplorationNode.md)\]</code>) – The entities reached, in the order they were found.
- [**edges**](#agrag-common-data_models-entity_search-ExplorationResult-edges) (<code>list\[[ExplorationEdge](ExplorationEdge.md)\]</code>) – The edges followed, in the order they were found.
- [**truncated**](#agrag-common-data_models-entity_search-ExplorationResult-truncated) (<code>bool</code>) – True when a bound cut the exploration.
- [**truncated_by**](#agrag-common-data_models-entity_search-ExplorationResult-truncated_by) (<code>list\[[ExplorationBound](ExplorationBound.md)\]</code>) – The bounds that cut the exploration.
- [**detail**](#agrag-common-data_models-entity_search-ExplorationResult-detail) (<code>str | None</code>) – A short message for a malformed or failed id. None otherwise.

## `detail` \{#agrag-common-data_models-entity_search-ExplorationResult-detail}

```python
detail: str | None = None
```

## `edges` \{#agrag-common-data_models-entity_search-ExplorationResult-edges}

```python
edges: list[ExplorationEdge] = Field(default_factory=list)
```

## `nodes` \{#agrag-common-data_models-entity_search-ExplorationResult-nodes}

```python
nodes: list[ExplorationNode] = Field(default_factory=list)
```

## `status` \{#agrag-common-data_models-entity_search-ExplorationResult-status}

```python
status: ExplorationStatus
```

## `truncated` \{#agrag-common-data_models-entity_search-ExplorationResult-truncated}

```python
truncated: bool = False
```

## `truncated_by` \{#agrag-common-data_models-entity_search-ExplorationResult-truncated_by}

```python
truncated_by: list[ExplorationBound] = Field(default_factory=list)
```
