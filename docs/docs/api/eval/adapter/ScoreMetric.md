---
title: agrag.eval.adapter.ScoreMetric
sidebar_label: ScoreMetric
---

# `agrag.eval.adapter.ScoreMetric` \{#agrag-eval-adapter-ScoreMetric}

```python
ScoreMetric(name:str, scorer:Callable[[LLMTestCase], ScoreResult], threshold:float = 0.5) -> None
```

Bases: <code>BaseMetric</code>

A DeepEval metric backed by a plain scoring function.

Use it for scores that DeepEval does not compute, such as F1 from
scikit-learn, so they report through the same `evaluate()` call.
If the scorer raises, the error is stored in `error` and raised again.

**Attributes:**

- [**name**](#agrag-eval-adapter-ScoreMetric-name) – The metric name shown in reports.
- [**scorer**](#agrag-eval-adapter-ScoreMetric-scorer) – The function that turns a test case into a `ScoreResult`.
- [**threshold**](#agrag-eval-adapter-ScoreMetric-threshold) – The minimum score that counts as success.

**Functions:**

- [**a_measure**](#agrag-eval-adapter-ScoreMetric-a_measure) – Run `measure`; scoring functions are synchronous.
- [**measure**](#agrag-eval-adapter-ScoreMetric-measure) – Run the scorer and record its score, reason and breakdown.

## `a_measure` \{#agrag-eval-adapter-ScoreMetric-a_measure}

```python
a_measure(test_case:LLMTestCase, *args:Any, **kwargs:Any) -> float
```

Run `measure`; scoring functions are synchronous.

## `measure` \{#agrag-eval-adapter-ScoreMetric-measure}

```python
measure(test_case:LLMTestCase, *args:Any, **kwargs:Any) -> float
```

Run the scorer and record its score, reason and breakdown.

## `name` \{#agrag-eval-adapter-ScoreMetric-name}

```python
name = name
```

## `scorer` \{#agrag-eval-adapter-ScoreMetric-scorer}

```python
scorer = scorer
```

## `threshold` \{#agrag-eval-adapter-ScoreMetric-threshold}

```python
threshold = threshold
```
