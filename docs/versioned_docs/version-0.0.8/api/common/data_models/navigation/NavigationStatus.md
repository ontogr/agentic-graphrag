---
title: agrag.common.data_models.navigation.NavigationStatus
sidebar_label: NavigationStatus
---

# `agrag.common.data_models.navigation.NavigationStatus` \{#agrag-common-data_models-navigation-NavigationStatus}

Bases: <code>StrEnum</code>

The outcome of a navigation call.

**Attributes:**

- [**OK**](#agrag-common-data_models-navigation-NavigationStatus-OK) – At least one item is returned.
- [**NO_MATCH**](#agrag-common-data_models-navigation-NavigationStatus-NO_MATCH) – The passage exists, but the relation has no items for it.
- [**UNAVAILABLE**](#agrag-common-data_models-navigation-NavigationStatus-UNAVAILABLE) – The id names no evidence this caller may read. Missing ids
  and ids outside the scope give this same outcome.
- [**MALFORMED**](#agrag-common-data_models-navigation-NavigationStatus-MALFORMED) – The id does not decode.
- [**FAILED**](#agrag-common-data_models-navigation-NavigationStatus-FAILED) – The store failed while reading the neighbors.

## `FAILED` \{#agrag-common-data_models-navigation-NavigationStatus-FAILED}

```python
FAILED = 'failed'
```

## `MALFORMED` \{#agrag-common-data_models-navigation-NavigationStatus-MALFORMED}

```python
MALFORMED = 'malformed'
```

## `NO_MATCH` \{#agrag-common-data_models-navigation-NavigationStatus-NO_MATCH}

```python
NO_MATCH = 'no_match'
```

## `OK` \{#agrag-common-data_models-navigation-NavigationStatus-OK}

```python
OK = 'ok'
```

## `UNAVAILABLE` \{#agrag-common-data_models-navigation-NavigationStatus-UNAVAILABLE}

```python
UNAVAILABLE = 'unavailable'
```
