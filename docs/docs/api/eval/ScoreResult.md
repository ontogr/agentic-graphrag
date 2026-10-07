---
title: agrag.eval.ScoreResult
sidebar_label: ScoreResult
---

# `agrag.eval.ScoreResult` \{#agrag-eval-ScoreResult}

Bases: <code>NamedTuple</code>

The outcome of one scoring function call.

**Attributes:**

- [**score**](#agrag-eval-ScoreResult-score) (<code>float</code>) – The score, normally between 0 and 1.
- [**reason**](#agrag-eval-ScoreResult-reason) (<code>str</code>) – A short explanation shown in DeepEval reports.
- [**breakdown**](#agrag-eval-ScoreResult-breakdown) (<code>dict\[str, Any\]</code>) – Extra numbers behind the score, such as per-class values.

## `breakdown` \{#agrag-eval-ScoreResult-breakdown}

```python
breakdown: dict[str, Any]
```

## `reason` \{#agrag-eval-ScoreResult-reason}

```python
reason: str
```

## `score` \{#agrag-eval-ScoreResult-score}

```python
score: float
```
