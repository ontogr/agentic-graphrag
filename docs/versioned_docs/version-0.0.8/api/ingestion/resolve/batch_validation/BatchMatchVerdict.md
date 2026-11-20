---
title: agrag.ingestion.resolve.batch_validation.BatchMatchVerdict
sidebar_label: BatchMatchVerdict
---

# `agrag.ingestion.resolve.batch_validation.BatchMatchVerdict` \{#agrag-ingestion-resolve-batch_validation-BatchMatchVerdict}

Bases: <code>BaseModel</code>

One LLM result bound to the candidate pair it judged.

**Attributes:**

- [**pair_id**](#agrag-ingestion-resolve-batch_validation-BatchMatchVerdict-pair_id) (<code>str</code>) –
- [**reasoning**](#agrag-ingestion-resolve-batch_validation-BatchMatchVerdict-reasoning) (<code>str | None</code>) –
- [**verdict**](#agrag-ingestion-resolve-batch_validation-BatchMatchVerdict-verdict) (<code>[ComparisonVerdict](../resolver/ComparisonVerdict.md)</code>) –

## `pair_id` \{#agrag-ingestion-resolve-batch_validation-BatchMatchVerdict-pair_id}

```python
pair_id: str
```

## `reasoning` \{#agrag-ingestion-resolve-batch_validation-BatchMatchVerdict-reasoning}

```python
reasoning: str | None = None
```

## `verdict` \{#agrag-ingestion-resolve-batch_validation-BatchMatchVerdict-verdict}

```python
verdict: ComparisonVerdict
```
