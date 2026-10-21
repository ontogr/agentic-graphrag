---
title: agrag.common.data_models.evidence.EvidenceSearchStatus
sidebar_label: EvidenceSearchStatus
---

# `agrag.common.data_models.evidence.EvidenceSearchStatus` \{#agrag-common-data_models-evidence-EvidenceSearchStatus}

Bases: <code>StrEnum</code>

The overall outcome of a search call.

**Attributes:**

- [**OK**](#agrag-common-data_models-evidence-EvidenceSearchStatus-OK) – Every leg ran and returned hits.
- [**PARTIAL**](#agrag-common-data_models-evidence-EvidenceSearchStatus-PARTIAL) – At least one leg failed, and the other leg returned hits. Read
  `EvidenceSearchResult.failures` before treating the list as complete.
- [**NO_MATCH**](#agrag-common-data_models-evidence-EvidenceSearchStatus-NO_MATCH) – Every leg ran and no visible passage matched.
- [**EMPTY_SCOPE**](#agrag-common-data_models-evidence-EvidenceSearchStatus-EMPTY_SCOPE) – The scope named no documents, so nothing was searched.
- [**INDEX_NOT_READY**](#agrag-common-data_models-evidence-EvidenceSearchStatus-INDEX_NOT_READY) – A search index the mode needs is missing or not ONLINE.
- [**FAILED**](#agrag-common-data_models-evidence-EvidenceSearchStatus-FAILED) – Every leg that ran failed.

## `EMPTY_SCOPE` \{#agrag-common-data_models-evidence-EvidenceSearchStatus-EMPTY_SCOPE}

```python
EMPTY_SCOPE = 'empty_scope'
```

## `FAILED` \{#agrag-common-data_models-evidence-EvidenceSearchStatus-FAILED}

```python
FAILED = 'failed'
```

## `INDEX_NOT_READY` \{#agrag-common-data_models-evidence-EvidenceSearchStatus-INDEX_NOT_READY}

```python
INDEX_NOT_READY = 'index_not_ready'
```

## `NO_MATCH` \{#agrag-common-data_models-evidence-EvidenceSearchStatus-NO_MATCH}

```python
NO_MATCH = 'no_match'
```

## `OK` \{#agrag-common-data_models-evidence-EvidenceSearchStatus-OK}

```python
OK = 'ok'
```

## `PARTIAL` \{#agrag-common-data_models-evidence-EvidenceSearchStatus-PARTIAL}

```python
PARTIAL = 'partial'
```
