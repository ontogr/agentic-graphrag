---
title: agrag.common.data_models.entity_search.EntityResult
sidebar_label: EntityResult
---

# `agrag.common.data_models.entity_search.EntityResult` \{#agrag-common-data_models-entity_search-EntityResult}

Bases: <code>BaseModel</code>

The result of one entity discovery call.

**Attributes:**

- [**status**](#agrag-common-data_models-entity_search-EntityResult-status) (<code>[DiscoveryStatus](../evidence/DiscoveryStatus.md)</code>) – The overall outcome. A failed leg never shows as NO_MATCH.
- [**hits**](#agrag-common-data_models-entity_search-EntityResult-hits) (<code>list\[[EntityHit](EntityHit.md)\]</code>) – The entities, best first.
- [**truncated**](#agrag-common-data_models-entity_search-EntityResult-truncated) (<code>bool</code>) – True when a search leg reached its candidate ceiling and
  fewer than `limit` entities were returned.
- [**index_state**](#agrag-common-data_models-entity_search-EntityResult-index_state) (<code>[IndexState](../evidence/IndexState.md) | None</code>) – Whether the needed indexes were ready. None when no index
  was checked.
- [**failures**](#agrag-common-data_models-entity_search-EntityResult-failures) (<code>list\[[LegFailure](../evidence/LegFailure.md)\]</code>) – The legs that failed. Empty when every leg ran.

## `failures` \{#agrag-common-data_models-entity_search-EntityResult-failures}

```python
failures: list[LegFailure] = Field(default_factory=list)
```

## `hits` \{#agrag-common-data_models-entity_search-EntityResult-hits}

```python
hits: list[EntityHit] = Field(default_factory=list)
```

## `index_state` \{#agrag-common-data_models-entity_search-EntityResult-index_state}

```python
index_state: IndexState | None = None
```

## `status` \{#agrag-common-data_models-entity_search-EntityResult-status}

```python
status: DiscoveryStatus
```

## `truncated` \{#agrag-common-data_models-entity_search-EntityResult-truncated}

```python
truncated: bool = False
```
