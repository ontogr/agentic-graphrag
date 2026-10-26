---
title: agrag.common.data_models.candidate_review.ApprovalResult
sidebar_label: ApprovalResult
---

# `agrag.common.data_models.candidate_review.ApprovalResult` \{#agrag-common-data_models-candidate_review-ApprovalResult}

Bases: <code>BaseModel</code>

Report approvals and the patch built from them.

**Attributes:**

- [**outcome**](#agrag-common-data_models-candidate_review-ApprovalResult-outcome) (<code>[ReviewOutcome](ReviewOutcome.md)</code>) – Groups approved or skipped during the operation.
- [**patch**](#agrag-common-data_models-candidate_review-ApprovalResult-patch) (<code>[SchemaPatch](SchemaPatch.md) | None</code>) – Schema patch for successful approvals, if any.
- [**path**](#agrag-common-data_models-candidate_review-ApprovalResult-path) (<code>str | None</code>) – Path of the written patch file, if requested and created.

## `outcome` \{#agrag-common-data_models-candidate_review-ApprovalResult-outcome}

```python
outcome: ReviewOutcome
```

## `patch` \{#agrag-common-data_models-candidate_review-ApprovalResult-patch}

```python
patch: SchemaPatch | None = None
```

## `path` \{#agrag-common-data_models-candidate_review-ApprovalResult-path}

```python
path: str | None = None
```
