---
title: agrag.candidates.ApprovalResult
sidebar_label: ApprovalResult
---

# `agrag.candidates.ApprovalResult` \{#agrag-candidates-ApprovalResult}

Bases: <code>BaseModel</code>

Report approvals and the patch built from them.

**Attributes:**

- [**outcome**](#agrag-candidates-ApprovalResult-outcome) (<code>[ReviewOutcome](../common/data_models/candidate_review/ReviewOutcome.md)</code>) – Groups approved or skipped during the operation.
- [**patch**](#agrag-candidates-ApprovalResult-patch) (<code>[SchemaPatch](../common/data_models/candidate_review/SchemaPatch.md) | None</code>) – Schema patch for successful approvals, if any.
- [**path**](#agrag-candidates-ApprovalResult-path) (<code>str | None</code>) – Path of the written patch file, if requested and created.

## `outcome` \{#agrag-candidates-ApprovalResult-outcome}

```python
outcome: ReviewOutcome
```

## `patch` \{#agrag-candidates-ApprovalResult-patch}

```python
patch: SchemaPatch | None = None
```

## `path` \{#agrag-candidates-ApprovalResult-path}

```python
path: str | None = None
```
