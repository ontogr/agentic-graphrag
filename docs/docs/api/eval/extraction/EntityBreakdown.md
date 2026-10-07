---
title: agrag.eval.extraction.EntityBreakdown
sidebar_label: EntityBreakdown
---

# `agrag.eval.extraction.EntityBreakdown` \{#agrag-eval-extraction-EntityBreakdown}

Bases: <code>[RelationBreakdown](RelationBreakdown.md)</code>

The `score_breakdown` of an entity quality metric for one case.

`per_label` counts the exact-match results for each entity label.

**Attributes:**

- [**kind**](#agrag-eval-extraction-EntityBreakdown-kind) (<code>Literal['entity', 'relation']</code>) –
- [**per_label**](#agrag-eval-extraction-EntityBreakdown-per_label) (<code>dict\[str, [LabelCounts](LabelCounts.md)\]</code>) –
- [**relaxed_y_pred**](#agrag-eval-extraction-EntityBreakdown-relaxed_y_pred) (<code>list\[int\]</code>) –
- [**relaxed_y_true**](#agrag-eval-extraction-EntityBreakdown-relaxed_y_true) (<code>list\[int\]</code>) –
- [**y_pred**](#agrag-eval-extraction-EntityBreakdown-y_pred) (<code>list\[int\]</code>) –
- [**y_true**](#agrag-eval-extraction-EntityBreakdown-y_true) (<code>list\[int\]</code>) –

## `kind` \{#agrag-eval-extraction-EntityBreakdown-kind}

```python
kind: Literal['entity', 'relation']
```

## `per_label` \{#agrag-eval-extraction-EntityBreakdown-per_label}

```python
per_label: dict[str, LabelCounts]
```

## `relaxed_y_pred` \{#agrag-eval-extraction-EntityBreakdown-relaxed_y_pred}

```python
relaxed_y_pred: list[int]
```

## `relaxed_y_true` \{#agrag-eval-extraction-EntityBreakdown-relaxed_y_true}

```python
relaxed_y_true: list[int]
```

## `y_pred` \{#agrag-eval-extraction-EntityBreakdown-y_pred}

```python
y_pred: list[int]
```

## `y_true` \{#agrag-eval-extraction-EntityBreakdown-y_true}

```python
y_true: list[int]
```
