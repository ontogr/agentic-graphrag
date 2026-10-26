---
title: agrag.candidates.PruneReport
sidebar_label: PruneReport
---

# `agrag.candidates.PruneReport` \{#agrag-candidates-PruneReport}

Bases: <code>BaseModel</code>

Report groups matched and deleted by a prune operation.

**Attributes:**

- [**matched**](#agrag-candidates-PruneReport-matched) (<code>int</code>) – Number of groups matching the prune criteria.
- [**deleted**](#agrag-candidates-PruneReport-deleted) (<code>int</code>) – Number of groups deleted.
- [**applied**](#agrag-candidates-PruneReport-applied) (<code>bool</code>) – Whether a deletion was performed.

## `applied` \{#agrag-candidates-PruneReport-applied}

```python
applied: bool
```

## `deleted` \{#agrag-candidates-PruneReport-deleted}

```python
deleted: int
```

## `matched` \{#agrag-candidates-PruneReport-matched}

```python
matched: int
```
