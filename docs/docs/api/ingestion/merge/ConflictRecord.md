---
title: agrag.ingestion.merge.ConflictRecord
sidebar_label: ConflictRecord
---

# `agrag.ingestion.merge.ConflictRecord` \{#agrag-ingestion-merge-ConflictRecord}

Bases: <code>BaseModel</code>

One property that had more than one candidate value.

**Attributes:**

- [**field**](#agrag-ingestion-merge-ConflictRecord-field) (<code>str</code>) – The property name.
- [**candidates**](#agrag-ingestion-merge-ConflictRecord-candidates) (<code>list\[object\]</code>) – Every distinct candidate value seen, in encounter order.
- [**resolved**](#agrag-ingestion-merge-ConflictRecord-resolved) (<code>object</code>) – The value compute_merge chose.

## `candidates` \{#agrag-ingestion-merge-ConflictRecord-candidates}

```python
candidates: list[object]
```

## `field` \{#agrag-ingestion-merge-ConflictRecord-field}

```python
field: str
```

## `resolved` \{#agrag-ingestion-merge-ConflictRecord-resolved}

```python
resolved: object
```
