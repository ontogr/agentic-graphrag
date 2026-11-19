---
title: agrag.common.data_models.navigation.NavigationResult
sidebar_label: NavigationResult
---

# `agrag.common.data_models.navigation.NavigationResult` \{#agrag-common-data_models-navigation-NavigationResult}

Bases: <code>BaseModel</code>

The result of one navigation call.

**Attributes:**

- [**status**](#agrag-common-data_models-navigation-NavigationResult-status) (<code>[NavigationStatus](NavigationStatus.md)</code>) – The overall outcome.
- [**items**](#agrag-common-data_models-navigation-NavigationResult-items) (<code>list\[[NavigationItem](NavigationItem.md)\]</code>) – The passages, in the order of the relation.
- [**truncated**](#agrag-common-data_models-navigation-NavigationResult-truncated) (<code>bool</code>) – True when a bound cut the items or the text.
- [**truncation_reason**](#agrag-common-data_models-navigation-NavigationResult-truncation_reason) (<code>[TruncationReason](TruncationReason.md) | None</code>) – The bound that cut the result, when `truncated`.
- [**version_status**](#agrag-common-data_models-navigation-NavigationResult-version_status) (<code>[VersionStatus](../evidence/VersionStatus.md) | None</code>) – Whether the version of the starting passage is current.
  None when no passage was resolved.
- [**multi_section**](#agrag-common-data_models-navigation-NavigationResult-multi_section) (<code>bool</code>) – True when the starting passage covers more than one
  section, so `parent` returns one item per section.
- [**detail**](#agrag-common-data_models-navigation-NavigationResult-detail) (<code>str | None</code>) – A short message for a malformed or failed id. None otherwise.

## `detail` \{#agrag-common-data_models-navigation-NavigationResult-detail}

```python
detail: str | None = None
```

## `items` \{#agrag-common-data_models-navigation-NavigationResult-items}

```python
items: list[NavigationItem] = Field(default_factory=list)
```

## `multi_section` \{#agrag-common-data_models-navigation-NavigationResult-multi_section}

```python
multi_section: bool = False
```

## `status` \{#agrag-common-data_models-navigation-NavigationResult-status}

```python
status: NavigationStatus
```

## `truncated` \{#agrag-common-data_models-navigation-NavigationResult-truncated}

```python
truncated: bool = False
```

## `truncation_reason` \{#agrag-common-data_models-navigation-NavigationResult-truncation_reason}

```python
truncation_reason: TruncationReason | None = None
```

## `version_status` \{#agrag-common-data_models-navigation-NavigationResult-version_status}

```python
version_status: VersionStatus | None = None
```
