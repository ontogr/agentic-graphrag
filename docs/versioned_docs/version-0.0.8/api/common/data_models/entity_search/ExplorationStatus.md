---
title: agrag.common.data_models.entity_search.ExplorationStatus
sidebar_label: ExplorationStatus
---

# `agrag.common.data_models.entity_search.ExplorationStatus` \{#agrag-common-data_models-entity_search-ExplorationStatus}

Bases: <code>StrEnum</code>

The outcome of an exploration call.

**Attributes:**

- [**OK**](#agrag-common-data_models-entity_search-ExplorationStatus-OK) – The exploration ran. It may hold no edges.
- [**UNAVAILABLE**](#agrag-common-data_models-entity_search-ExplorationStatus-UNAVAILABLE) – The start entity is missing, or no passage of it is in
  scope. Both cases give this same outcome.
- [**MALFORMED**](#agrag-common-data_models-entity_search-ExplorationStatus-MALFORMED) – The entity id is not a canonical UUID string.
- [**FAILED**](#agrag-common-data_models-entity_search-ExplorationStatus-FAILED) – The store failed while exploring.

## `FAILED` \{#agrag-common-data_models-entity_search-ExplorationStatus-FAILED}

```python
FAILED = 'failed'
```

## `MALFORMED` \{#agrag-common-data_models-entity_search-ExplorationStatus-MALFORMED}

```python
MALFORMED = 'malformed'
```

## `OK` \{#agrag-common-data_models-entity_search-ExplorationStatus-OK}

```python
OK = 'ok'
```

## `UNAVAILABLE` \{#agrag-common-data_models-entity_search-ExplorationStatus-UNAVAILABLE}

```python
UNAVAILABLE = 'unavailable'
```
