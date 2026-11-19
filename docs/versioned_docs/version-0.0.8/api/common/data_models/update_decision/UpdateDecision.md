---
title: agrag.common.data_models.update_decision.UpdateDecision
sidebar_label: UpdateDecision
---

# `agrag.common.data_models.update_decision.UpdateDecision` \{#agrag-common-data_models-update_decision-UpdateDecision}

Bases: <code>StrEnum</code>

What an update does with a document already in the graph.

**Attributes:**

- [**NO_OP**](#agrag-common-data_models-update_decision-UpdateDecision-NO_OP) – The stored input matches and no refresh was requested.
- [**IN_PLACE**](#agrag-common-data_models-update_decision-UpdateDecision-IN_PLACE) – Extraction runs again while chunks and embeddings stay.
- [**NEW_VERSION**](#agrag-common-data_models-update_decision-UpdateDecision-NEW_VERSION) – Changed content, chunking or schema requires new chunks.
- [**METADATA_ONLY**](#agrag-common-data_models-update_decision-UpdateDecision-METADATA_ONLY) – Only the document dates are written.

## `IN_PLACE` \{#agrag-common-data_models-update_decision-UpdateDecision-IN_PLACE}

```python
IN_PLACE = 'in_place'
```

## `METADATA_ONLY` \{#agrag-common-data_models-update_decision-UpdateDecision-METADATA_ONLY}

```python
METADATA_ONLY = 'metadata_only'
```

## `NEW_VERSION` \{#agrag-common-data_models-update_decision-UpdateDecision-NEW_VERSION}

```python
NEW_VERSION = 'new_version'
```

## `NO_OP` \{#agrag-common-data_models-update_decision-UpdateDecision-NO_OP}

```python
NO_OP = 'no_op'
```
