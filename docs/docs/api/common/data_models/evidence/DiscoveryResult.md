---
title: agrag.common.data_models.evidence.DiscoveryResult
sidebar_label: DiscoveryResult
---

# `agrag.common.data_models.evidence.DiscoveryResult` \{#agrag-common-data_models-evidence-DiscoveryResult}

Bases: <code>BaseModel</code>

The result of one discovery call.

**Attributes:**

- [**status**](#agrag-common-data_models-evidence-DiscoveryResult-status) (<code>[DiscoveryStatus](DiscoveryStatus.md)</code>) – The overall outcome. A failed leg never shows as NO_MATCH.
- [**hits**](#agrag-common-data_models-evidence-DiscoveryResult-hits) (<code>list\[[DiscoveryHit](DiscoveryHit.md)\]</code>) – The visible passages, best first. Empty unless status is OK or
  PARTIAL.
- [**truncated**](#agrag-common-data_models-evidence-DiscoveryResult-truncated) (<code>bool</code>) – True when the search reached its candidate ceiling before it
  found `limit` visible passages, so more passages may exist.
- [**index_state**](#agrag-common-data_models-evidence-DiscoveryResult-index_state) (<code>[IndexState](IndexState.md) | None</code>) – Whether the needed indexes were ready. None when no index
  was checked, which happens for an empty scope.
- [**failures**](#agrag-common-data_models-evidence-DiscoveryResult-failures) (<code>list\[[LegFailure](LegFailure.md)\]</code>) – The legs that failed. Empty when every leg ran.

## `failures` \{#agrag-common-data_models-evidence-DiscoveryResult-failures}

```python
failures: list[LegFailure] = Field(default_factory=list)
```

## `hits` \{#agrag-common-data_models-evidence-DiscoveryResult-hits}

```python
hits: list[DiscoveryHit] = Field(default_factory=list)
```

## `index_state` \{#agrag-common-data_models-evidence-DiscoveryResult-index_state}

```python
index_state: IndexState | None = None
```

## `status` \{#agrag-common-data_models-evidence-DiscoveryResult-status}

```python
status: DiscoveryStatus
```

## `truncated` \{#agrag-common-data_models-evidence-DiscoveryResult-truncated}

```python
truncated: bool = False
```
