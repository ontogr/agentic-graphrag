---
title: agrag.common.data_models.evidence.FetchStatus
sidebar_label: FetchStatus
---

# `agrag.common.data_models.evidence.FetchStatus` \{#agrag-common-data_models-evidence-FetchStatus}

Bases: <code>StrEnum</code>

The outcome of fetching one evidence id.

**Attributes:**

- [**OK**](#agrag-common-data_models-evidence-FetchStatus-OK) – The text is returned in full.
- [**PARTIAL**](#agrag-common-data_models-evidence-FetchStatus-PARTIAL) – Part of the requested range is covered by no chunk. Only the covered
  part is returned. An id from this outcome names more text than the
  caller received, so it must not be cited as fetched.
- [**TRUNCATED**](#agrag-common-data_models-evidence-FetchStatus-TRUNCATED) – The text was cut at `max_chars`.
- [**UNAVAILABLE**](#agrag-common-data_models-evidence-FetchStatus-UNAVAILABLE) – The id names no evidence this caller may read. Missing ids
  and ids outside the scope give this same outcome.
- [**MALFORMED**](#agrag-common-data_models-evidence-FetchStatus-MALFORMED) – The id does not decode.
- [**INDEX_NOT_READY**](#agrag-common-data_models-evidence-FetchStatus-INDEX_NOT_READY) – A search index the operation needs is not ready.
  Fetch uses no index, so it does not return this status.
- [**FAILED**](#agrag-common-data_models-evidence-FetchStatus-FAILED) – The store failed while reading the evidence.

## `FAILED` \{#agrag-common-data_models-evidence-FetchStatus-FAILED}

```python
FAILED = 'failed'
```

## `INDEX_NOT_READY` \{#agrag-common-data_models-evidence-FetchStatus-INDEX_NOT_READY}

```python
INDEX_NOT_READY = 'index_not_ready'
```

## `MALFORMED` \{#agrag-common-data_models-evidence-FetchStatus-MALFORMED}

```python
MALFORMED = 'malformed'
```

## `OK` \{#agrag-common-data_models-evidence-FetchStatus-OK}

```python
OK = 'ok'
```

## `PARTIAL` \{#agrag-common-data_models-evidence-FetchStatus-PARTIAL}

```python
PARTIAL = 'partial'
```

## `TRUNCATED` \{#agrag-common-data_models-evidence-FetchStatus-TRUNCATED}

```python
TRUNCATED = 'truncated'
```

## `UNAVAILABLE` \{#agrag-common-data_models-evidence-FetchStatus-UNAVAILABLE}

```python
UNAVAILABLE = 'unavailable'
```
