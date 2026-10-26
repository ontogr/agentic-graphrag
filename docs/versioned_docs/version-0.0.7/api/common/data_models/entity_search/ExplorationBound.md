---
title: agrag.common.data_models.entity_search.ExplorationBound
sidebar_label: ExplorationBound
---

# `agrag.common.data_models.entity_search.ExplorationBound` \{#agrag-common-data_models-entity_search-ExplorationBound}

Bases: <code>StrEnum</code>

A bound that cut an exploration.

**Attributes:**

- [**NODES**](#agrag-common-data_models-entity_search-ExplorationBound-NODES) – More entities were reached than `max_nodes` allows.
- [**EDGES**](#agrag-common-data_models-entity_search-ExplorationBound-EDGES) – More edges existed than `max_edges` allows.
- [**DEPTH**](#agrag-common-data_models-entity_search-ExplorationBound-DEPTH) – Entities at the last allowed depth have further connections that
  were not followed.
- [**CANDIDATES**](#agrag-common-data_models-entity_search-ExplorationBound-CANDIDATES) – More relations existed than the per-frontier read limit.

## `CANDIDATES` \{#agrag-common-data_models-entity_search-ExplorationBound-CANDIDATES}

```python
CANDIDATES = 'candidates'
```

## `DEPTH` \{#agrag-common-data_models-entity_search-ExplorationBound-DEPTH}

```python
DEPTH = 'depth'
```

## `EDGES` \{#agrag-common-data_models-entity_search-ExplorationBound-EDGES}

```python
EDGES = 'edges'
```

## `NODES` \{#agrag-common-data_models-entity_search-ExplorationBound-NODES}

```python
NODES = 'nodes'
```
