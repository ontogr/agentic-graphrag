---
title: agrag.common.data_models.candidate_review.ReviewOutcome
sidebar_label: ReviewOutcome
---

# `agrag.common.data_models.candidate_review.ReviewOutcome` \{#agrag-common-data_models-candidate_review-ReviewOutcome}

Bases: <code>BaseModel</code>

Report candidate groups moved and groups that could not be moved.

**Attributes:**

- [**changed**](#agrag-common-data_models-candidate_review-ReviewOutcome-changed) (<code>list\[str\]</code>) – Keys whose groups changed state.
- [**skipped**](#agrag-common-data_models-candidate_review-ReviewOutcome-skipped) (<code>dict\[str, str\]</code>) – Keys not changed, mapped to the reason they were skipped.

## `changed` \{#agrag-common-data_models-candidate_review-ReviewOutcome-changed}

```python
changed: list[str] = Field(default_factory=list)
```

## `skipped` \{#agrag-common-data_models-candidate_review-ReviewOutcome-skipped}

```python
skipped: dict[str, str] = Field(default_factory=dict)
```
