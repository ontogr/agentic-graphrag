---
title: agrag.candidates.CandidateQuery
sidebar_label: CandidateQuery
---

# `agrag.candidates.CandidateQuery` \{#agrag-candidates-CandidateQuery}

Bases: <code>BaseModel</code>

Filter candidate groups by kind, label, state, and total sightings.

**Attributes:**

- [**kind**](#agrag-candidates-CandidateQuery-kind) (<code>[CandidateKind](../common/data_models/candidate/CandidateKind.md) | None</code>) – Candidate kind to include, or all kinds when unset.
- [**label**](#agrag-candidates-CandidateQuery-label) (<code>str | None</code>) – Exact candidate label to include, or all labels when unset.
- [**state**](#agrag-candidates-CandidateQuery-state) (<code>[CandidateState](../common/data_models/candidate/CandidateState.md) | None</code>) – Review state to include. Defaults to pending candidates.
- [**min_count**](#agrag-candidates-CandidateQuery-min_count) (<code>int</code>) – Minimum aggregate sighting count, at least one.

## `kind` \{#agrag-candidates-CandidateQuery-kind}

```python
kind: CandidateKind | None = None
```

## `label` \{#agrag-candidates-CandidateQuery-label}

```python
label: str | None = None
```

## `min_count` \{#agrag-candidates-CandidateQuery-min_count}

```python
min_count: int = Field(default=1, ge=1)
```

## `model_config` \{#agrag-candidates-CandidateQuery-model_config}

```python
model_config = ConfigDict(frozen=True)
```

## `state` \{#agrag-candidates-CandidateQuery-state}

```python
state: CandidateState | None = 'pending'
```
