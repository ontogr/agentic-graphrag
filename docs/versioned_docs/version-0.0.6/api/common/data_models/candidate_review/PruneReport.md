---
title: agrag.common.data_models.candidate_review.PruneReport
sidebar_label: PruneReport
---

# `agrag.common.data_models.candidate_review.PruneReport` \{#agrag-common-data_models-candidate_review-PruneReport}

Bases: <code>BaseModel</code>

Report groups matched and deleted by a prune operation.

**Attributes:**

- [**matched**](#agrag-common-data_models-candidate_review-PruneReport-matched) (<code>int</code>) – Number of groups matching the prune criteria.
- [**deleted**](#agrag-common-data_models-candidate_review-PruneReport-deleted) (<code>int</code>) – Number of groups deleted.
- [**applied**](#agrag-common-data_models-candidate_review-PruneReport-applied) (<code>bool</code>) – Whether a deletion was performed.

## `applied` \{#agrag-common-data_models-candidate_review-PruneReport-applied}

```python
applied: bool
```

## `deleted` \{#agrag-common-data_models-candidate_review-PruneReport-deleted}

```python
deleted: int
```

## `matched` \{#agrag-common-data_models-candidate_review-PruneReport-matched}

```python
matched: int
```
