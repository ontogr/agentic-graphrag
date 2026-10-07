---
title: agrag.eval.extraction.MicroScores
sidebar_label: MicroScores
---

# `agrag.eval.extraction.MicroScores` \{#agrag-eval-extraction-MicroScores}

Bases: <code>BaseModel</code>

Dataset scores pooled over every item, for entities and relations.

**Attributes:**

- [**entities_exact**](#agrag-eval-extraction-MicroScores-entities_exact) (<code>[Scores](Scores.md)</code>) – Entity scores with exact span matching.
- [**entities_relaxed**](#agrag-eval-extraction-MicroScores-entities_relaxed) (<code>[Scores](Scores.md)</code>) – Entity scores with overlap of at least 0.5.
- [**relations_exact**](#agrag-eval-extraction-MicroScores-relations_exact) (<code>[Scores](Scores.md)</code>) – Relation triple scores over exact entity alignment.
- [**relations_relaxed**](#agrag-eval-extraction-MicroScores-relations_relaxed) (<code>[Scores](Scores.md)</code>) – Relation triple scores over relaxed entity alignment.

## `entities_exact` \{#agrag-eval-extraction-MicroScores-entities_exact}

```python
entities_exact: Scores
```

## `entities_relaxed` \{#agrag-eval-extraction-MicroScores-entities_relaxed}

```python
entities_relaxed: Scores
```

## `relations_exact` \{#agrag-eval-extraction-MicroScores-relations_exact}

```python
relations_exact: Scores
```

## `relations_relaxed` \{#agrag-eval-extraction-MicroScores-relations_relaxed}

```python
relations_relaxed: Scores
```
