---
title: agrag.eval.CitationAccuracyMetric
sidebar_label: CitationAccuracyMetric
---

# `agrag.eval.CitationAccuracyMetric` \{#agrag-eval-CitationAccuracyMetric}

```python
CitationAccuracyMetric(judge:DeepEvalBaseLLM, *, threshold:float = 0.5) -> None
```

Bases: <code>BaseMetric</code>

Score whether each cited sentence follows from the evidence it cites.

The unit is the sentence. A sentence counts as cited when it carries a
citation key. A judge decides whether the text of the cited evidence supports
the sentence. It scores each sentence with one `GEval` run. A cited key that
the run's ledger did not assign is fabricated: the sentence is unsupported and
no judge call happens.

The score is the F1 of two ratios. Precision is supported cited sentences
over cited sentences. Recall is supported cited sentences over all sentences
of at least four words, plus any shorter cited sentence. `score_breakdown`
holds both and the sentence counts. An answer with no citations scores 0. An
abstention, the exact text `No relevant evidence found.`, scores 1.
`score_breakdown` also holds one row per cited sentence with its keys,
fabricated flag, support verdict and judge reason.

The test case must come from `answer_case`, which puts the evidence under
`metadata["citations"]`. A judge failure on any sentence raises.

**Attributes:**

- [**judge**](#agrag-eval-CitationAccuracyMetric-judge) – The judge model.
- [**threshold**](#agrag-eval-CitationAccuracyMetric-threshold) – The minimum score that counts as success, and the minimum
  support score for one sentence.
- [**score_breakdown**](#agrag-eval-CitationAccuracyMetric-score_breakdown) (<code>[CitationScoreBreakdown](answer/CitationScoreBreakdown.md)</code>) – Precision, recall, and sentence counts for the score.

**Functions:**

- [**a_measure**](#agrag-eval-CitationAccuracyMetric-a_measure) – Judge the cited sentences with up to eight concurrent calls.
- [**measure**](#agrag-eval-CitationAccuracyMetric-measure) – Judge the cited sentences one after the other.

## `a_measure` \{#agrag-eval-CitationAccuracyMetric-a_measure}

```python
a_measure(test_case:LLMTestCase, *args:Any, **kwargs:Any) -> float
```

Judge the cited sentences with up to eight concurrent calls.

**Parameters:**

- **test_case** (<code>LLMTestCase</code>) – The test case built by `answer_case`.
- \***args** (<code>Any</code>) – Additional positional arguments accepted by DeepEval.
- \*\***kwargs** (<code>Any</code>) – Additional keyword arguments accepted by DeepEval.

**Returns:**

- <code>float</code> – The citation accuracy score.

## `judge` \{#agrag-eval-CitationAccuracyMetric-judge}

```python
judge = judge
```

## `measure` \{#agrag-eval-CitationAccuracyMetric-measure}

```python
measure(test_case:LLMTestCase, *args:Any, **kwargs:Any) -> float
```

Judge the cited sentences one after the other.

**Parameters:**

- **test_case** (<code>LLMTestCase</code>) – The test case built by `answer_case`.
- \***args** (<code>Any</code>) – Additional positional arguments accepted by DeepEval.
- \*\***kwargs** (<code>Any</code>) – Additional keyword arguments accepted by DeepEval.

**Returns:**

- <code>float</code> – The citation accuracy score.

## `score_breakdown` \{#agrag-eval-CitationAccuracyMetric-score_breakdown}

```python
score_breakdown: CitationScoreBreakdown
```

## `threshold` \{#agrag-eval-CitationAccuracyMetric-threshold}

```python
threshold = threshold
```
