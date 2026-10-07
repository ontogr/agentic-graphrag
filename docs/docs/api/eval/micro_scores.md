---
title: agrag.eval.micro_scores
sidebar_label: micro_scores
---

# `agrag.eval.micro_scores` \{#agrag-eval-micro_scores}

```python
micro_scores(metrics:Iterable[ScoreMetric]) -> MicroScores
```

Pool measured entity and relation metrics into dataset scores.

**Parameters:**

- **metrics** (<code>Iterable\[[ScoreMetric](adapter/ScoreMetric.md)\]</code>) – Metrics from `entity_quality_metric` and
  `relation_quality_metric`, after `measure`.

**Returns:**

- <code>[MicroScores](extraction/MicroScores.md)</code> – Pooled exact and relaxed scores for entities and relations.

**Raises:**

- <code>ValueError</code> – No entity metric or no relation metric was given.
