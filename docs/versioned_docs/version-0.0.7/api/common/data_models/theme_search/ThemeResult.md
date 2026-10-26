---
title: agrag.common.data_models.theme_search.ThemeResult
sidebar_label: ThemeResult
---

# `agrag.common.data_models.theme_search.ThemeResult` \{#agrag-common-data_models-theme_search-ThemeResult}

Bases: <code>BaseModel</code>

The result of one theme search call.

**Attributes:**

- [**status**](#agrag-common-data_models-theme_search-ThemeResult-status) (<code>[EvidenceSearchStatus](../evidence/EvidenceSearchStatus.md)</code>) – The overall outcome. A failed leg never shows as NO_MATCH.
- [**themes**](#agrag-common-data_models-theme_search-ThemeResult-themes) (<code>list\[[ThemeHit](ThemeHit.md)\]</code>) – The themes, best first.
- [**truncated**](#agrag-common-data_models-theme_search-ThemeResult-truncated) (<code>bool</code>) – True when fewer than `limit` themes remained and the vector
  read filled its candidate window, so more themes may exist.
- [**index_state**](#agrag-common-data_models-theme_search-ThemeResult-index_state) (<code>[IndexState](../evidence/IndexState.md) | None</code>) – Whether the needed index was ready. None when no index was
  checked.
- [**failures**](#agrag-common-data_models-theme_search-ThemeResult-failures) (<code>list\[[LegFailure](../evidence/LegFailure.md)\]</code>) – The legs that failed. Empty when every leg ran.

## `failures` \{#agrag-common-data_models-theme_search-ThemeResult-failures}

```python
failures: list[LegFailure] = Field(default_factory=list)
```

## `index_state` \{#agrag-common-data_models-theme_search-ThemeResult-index_state}

```python
index_state: IndexState | None = None
```

## `status` \{#agrag-common-data_models-theme_search-ThemeResult-status}

```python
status: EvidenceSearchStatus
```

## `themes` \{#agrag-common-data_models-theme_search-ThemeResult-themes}

```python
themes: list[ThemeHit] = Field(default_factory=list)
```

## `truncated` \{#agrag-common-data_models-theme_search-ThemeResult-truncated}

```python
truncated: bool = False
```
