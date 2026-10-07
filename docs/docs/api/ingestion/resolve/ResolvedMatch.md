---
title: agrag.ingestion.resolve.ResolvedMatch
sidebar_label: ResolvedMatch
---

# `agrag.ingestion.resolve.ResolvedMatch` \{#agrag-ingestion-resolve-ResolvedMatch}

Bases: <code>BaseModel</code>

One confirmed non-exact match between two input entity indices.

Exact-name identity matches group mentions but do not create a match-graph
edge. Every other confirmed comparator decision creates one record.

**Attributes:**

- [**comparator**](#agrag-ingestion-resolve-ResolvedMatch-comparator) (<code>str</code>) –
- [**decided_at**](#agrag-ingestion-resolve-ResolvedMatch-decided_at) (<code>datetime</code>) –
- [**left_index**](#agrag-ingestion-resolve-ResolvedMatch-left_index) (<code>int</code>) –
- [**reasoning**](#agrag-ingestion-resolve-ResolvedMatch-reasoning) (<code>str | None</code>) –
- [**right_index**](#agrag-ingestion-resolve-ResolvedMatch-right_index) (<code>int</code>) –
- [**score**](#agrag-ingestion-resolve-ResolvedMatch-score) (<code>float | None</code>) –

## `comparator` \{#agrag-ingestion-resolve-ResolvedMatch-comparator}

```python
comparator: str
```

## `decided_at` \{#agrag-ingestion-resolve-ResolvedMatch-decided_at}

```python
decided_at: datetime
```

## `left_index` \{#agrag-ingestion-resolve-ResolvedMatch-left_index}

```python
left_index: int
```

## `reasoning` \{#agrag-ingestion-resolve-ResolvedMatch-reasoning}

```python
reasoning: str | None = None
```

## `right_index` \{#agrag-ingestion-resolve-ResolvedMatch-right_index}

```python
right_index: int
```

## `score` \{#agrag-ingestion-resolve-ResolvedMatch-score}

```python
score: float | None = None
```
