---
title: agrag.common.data_models.candidate_review.CandidateGroup
sidebar_label: CandidateGroup
---

# `agrag.common.data_models.candidate_review.CandidateGroup` \{#agrag-common-data_models-candidate_review-CandidateGroup}

Bases: <code>BaseModel</code>

A deduplicated group of candidate nodes in one review state.

**Attributes:**

- [**key**](#agrag-common-data_models-candidate_review-CandidateGroup-key) (<code>str</code>) – Stable key shared by the grouped candidate nodes.
- [**state**](#agrag-common-data_models-candidate_review-CandidateGroup-state) (<code>[CandidateState](../candidate/CandidateState.md)</code>) – Current review state.
- [**count**](#agrag-common-data_models-candidate_review-CandidateGroup-count) (<code>int</code>) – Total sightings represented by the group.
- [**ids**](#agrag-common-data_models-candidate_review-CandidateGroup-ids) (<code>list\[UUID\]</code>) – Candidate node identifiers in the group.
- [**candidate**](#agrag-common-data_models-candidate_review-CandidateGroup-candidate) (<code>[CandidateRecord](../candidate/CandidateRecord.md)</code>) – Representative candidate record.
- [**chunk_ids**](#agrag-common-data_models-candidate_review-CandidateGroup-chunk_ids) (<code>list\[UUID\]</code>) – Source chunk identifiers, when available.
- [**document_count**](#agrag-common-data_models-candidate_review-CandidateGroup-document_count) (<code>int</code>) – Number of documents represented by the group.

**Functions:**

- [**from_row**](#agrag-common-data_models-candidate_review-CandidateGroup-from_row) – Build a group from a candidate-listing result row.

## `candidate` \{#agrag-common-data_models-candidate_review-CandidateGroup-candidate}

```python
candidate: CandidateRecord
```

## `chunk_ids` \{#agrag-common-data_models-candidate_review-CandidateGroup-chunk_ids}

```python
chunk_ids: list[UUID] = Field(default_factory=list)
```

## `count` \{#agrag-common-data_models-candidate_review-CandidateGroup-count}

```python
count: int
```

## `document_count` \{#agrag-common-data_models-candidate_review-CandidateGroup-document_count}

```python
document_count: int = 0
```

## `from_row` \{#agrag-common-data_models-candidate_review-CandidateGroup-from_row}

```python
from_row(row:Mapping[str, Any]) -> CandidateGroup
```

Build a group from a candidate-listing result row.

The row may contain a nested candidate record or candidate fields at
the top level. Aggregate count and confidence values are applied to
the representative record.

**Parameters:**

- **row** (<code>Mapping\[str, Any\]</code>) – Flat graph result row with a key, state, count, and ids.

**Returns:**

- <code>CandidateGroup</code> – Validated group with UUID identifiers.

**Raises:**

- <code>KeyError</code> – If a required result field is missing.
- <code>ValueError</code> – If an identifier or candidate field is invalid.

## `ids` \{#agrag-common-data_models-candidate_review-CandidateGroup-ids}

```python
ids: list[UUID]
```

## `key` \{#agrag-common-data_models-candidate_review-CandidateGroup-key}

```python
key: str
```

## `state` \{#agrag-common-data_models-candidate_review-CandidateGroup-state}

```python
state: CandidateState
```
