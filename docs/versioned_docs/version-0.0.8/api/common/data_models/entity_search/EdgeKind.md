---
title: agrag.common.data_models.entity_search.EdgeKind
sidebar_label: EdgeKind
---

# `agrag.common.data_models.entity_search.EdgeKind` \{#agrag-common-data_models-entity_search-EdgeKind}

Bases: <code>StrEnum</code>

Whether an exploration edge is supported by a passage.

**Attributes:**

- [**ASSERTION**](#agrag-common-data_models-entity_search-EdgeKind-ASSERTION) – The relation has visible supporting passages, which are listed
  in the edge.
- [**PATH**](#agrag-common-data_models-entity_search-EdgeKind-PATH) – The entities are connected in the graph, and no passage in scope
  states the relation. A path is not a fact, and a conclusion drawn
  from it needs its own support.

## `ASSERTION` \{#agrag-common-data_models-entity_search-EdgeKind-ASSERTION}

```python
ASSERTION = 'assertion'
```

## `PATH` \{#agrag-common-data_models-entity_search-EdgeKind-PATH}

```python
PATH = 'path'
```
