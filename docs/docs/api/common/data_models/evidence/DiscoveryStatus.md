---
title: agrag.common.data_models.evidence.DiscoveryStatus
sidebar_label: DiscoveryStatus
---

# `agrag.common.data_models.evidence.DiscoveryStatus` \{#agrag-common-data_models-evidence-DiscoveryStatus}

Bases: <code>StrEnum</code>

The overall outcome of a discovery call.

**Attributes:**

- [**OK**](#agrag-common-data_models-evidence-DiscoveryStatus-OK) – Every leg ran and returned hits.
- [**PARTIAL**](#agrag-common-data_models-evidence-DiscoveryStatus-PARTIAL) – At least one leg failed, and the other leg returned hits. Read
  `DiscoveryResult.failures` before treating the list as complete.
- [**NO_MATCH**](#agrag-common-data_models-evidence-DiscoveryStatus-NO_MATCH) – Every leg ran and no visible passage matched.
- [**EMPTY_SCOPE**](#agrag-common-data_models-evidence-DiscoveryStatus-EMPTY_SCOPE) – The scope named no documents, so nothing was searched.
- [**INDEX_NOT_READY**](#agrag-common-data_models-evidence-DiscoveryStatus-INDEX_NOT_READY) – A search index the mode needs is missing or not ONLINE.
- [**FAILED**](#agrag-common-data_models-evidence-DiscoveryStatus-FAILED) – Every leg that ran failed.

## `EMPTY_SCOPE` \{#agrag-common-data_models-evidence-DiscoveryStatus-EMPTY_SCOPE}

```python
EMPTY_SCOPE = 'empty_scope'
```

## `FAILED` \{#agrag-common-data_models-evidence-DiscoveryStatus-FAILED}

```python
FAILED = 'failed'
```

## `INDEX_NOT_READY` \{#agrag-common-data_models-evidence-DiscoveryStatus-INDEX_NOT_READY}

```python
INDEX_NOT_READY = 'index_not_ready'
```

## `NO_MATCH` \{#agrag-common-data_models-evidence-DiscoveryStatus-NO_MATCH}

```python
NO_MATCH = 'no_match'
```

## `OK` \{#agrag-common-data_models-evidence-DiscoveryStatus-OK}

```python
OK = 'ok'
```

## `PARTIAL` \{#agrag-common-data_models-evidence-DiscoveryStatus-PARTIAL}

```python
PARTIAL = 'partial'
```
