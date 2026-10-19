---
title: agrag.common.data_models.evidence.IndexState
sidebar_label: IndexState
---

# `agrag.common.data_models.evidence.IndexState` \{#agrag-common-data_models-evidence-IndexState}

Bases: <code>StrEnum</code>

Whether the search indexes a mode needs are ready.

**Attributes:**

- [**READY**](#agrag-common-data_models-evidence-IndexState-READY) – Every needed index exists and is ONLINE.
- [**NOT_READY**](#agrag-common-data_models-evidence-IndexState-NOT_READY) – At least one needed index is missing or not ONLINE.

## `NOT_READY` \{#agrag-common-data_models-evidence-IndexState-NOT_READY}

```python
NOT_READY = 'not_ready'
```

## `READY` \{#agrag-common-data_models-evidence-IndexState-READY}

```python
READY = 'ready'
```
