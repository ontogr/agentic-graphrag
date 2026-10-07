---
title: agrag.ingestion.resolve.ComparisonResult
sidebar_label: ComparisonResult
---

# `agrag.ingestion.resolve.ComparisonResult` \{#agrag-ingestion-resolve-ComparisonResult}

Bases: <code>BaseModel</code>

The verdict and evidence produced by one comparator.

**Attributes:**

- [**reasoning**](#agrag-ingestion-resolve-ComparisonResult-reasoning) (<code>str | None</code>) –
- [**score**](#agrag-ingestion-resolve-ComparisonResult-score) (<code>float | None</code>) –
- [**verdict**](#agrag-ingestion-resolve-ComparisonResult-verdict) (<code>[ComparisonVerdict](resolver/ComparisonVerdict.md)</code>) –

## `reasoning` \{#agrag-ingestion-resolve-ComparisonResult-reasoning}

```python
reasoning: str | None = None
```

## `score` \{#agrag-ingestion-resolve-ComparisonResult-score}

```python
score: float | None = None
```

## `verdict` \{#agrag-ingestion-resolve-ComparisonResult-verdict}

```python
verdict: ComparisonVerdict
```
