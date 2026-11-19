---
title: agrag.common.data_models.candidate_review.CandidateQuery
sidebar_label: CandidateQuery
---

# `agrag.common.data_models.candidate_review.CandidateQuery` \{#agrag-common-data_models-candidate_review-CandidateQuery}

Bases: <code>BaseModel</code>

Filter candidate groups by kind, label, state, and total sightings.

**Attributes:**

- [**kind**](#agrag-common-data_models-candidate_review-CandidateQuery-kind) (<code>[CandidateKind](../candidate/CandidateKind.md) | None</code>) – Candidate kind to include, or all kinds when unset.
- [**label**](#agrag-common-data_models-candidate_review-CandidateQuery-label) (<code>str | None</code>) – Exact candidate label to include, or all labels when unset.
- [**state**](#agrag-common-data_models-candidate_review-CandidateQuery-state) (<code>[CandidateState](../candidate/CandidateState.md) | None</code>) – Review state to include. Defaults to pending candidates.
- [**min_count**](#agrag-common-data_models-candidate_review-CandidateQuery-min_count) (<code>int</code>) – Minimum aggregate sighting count, at least one.

## `kind` \{#agrag-common-data_models-candidate_review-CandidateQuery-kind}

```python
kind: CandidateKind | None = None
```

## `label` \{#agrag-common-data_models-candidate_review-CandidateQuery-label}

```python
label: str | None = None
```

## `min_count` \{#agrag-common-data_models-candidate_review-CandidateQuery-min_count}

```python
min_count: int = Field(default=1, ge=1)
```

## `model_config` \{#agrag-common-data_models-candidate_review-CandidateQuery-model_config}

```python
model_config = ConfigDict(frozen=True)
```

## `state` \{#agrag-common-data_models-candidate_review-CandidateQuery-state}

```python
state: CandidateState | None = 'pending'
```
