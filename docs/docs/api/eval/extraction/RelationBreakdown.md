---
title: agrag.eval.extraction.RelationBreakdown
sidebar_label: RelationBreakdown
---

# `agrag.eval.extraction.RelationBreakdown` \{#agrag-eval-extraction-RelationBreakdown}

Bases: <code>TypedDict</code>

The `score_breakdown` of a relation quality metric for one case.

The label lists are 0/1 values over the union of gold and predicted items:
`y_true` marks gold items and `y_pred` marks predicted ones. The
`relaxed_` lists use an overlap of at least 0.5 to align entities.

**Attributes:**

- [**kind**](#agrag-eval-extraction-RelationBreakdown-kind) (<code>Literal['entity', 'relation']</code>) –
- [**relaxed_y_pred**](#agrag-eval-extraction-RelationBreakdown-relaxed_y_pred) (<code>list\[int\]</code>) –
- [**relaxed_y_true**](#agrag-eval-extraction-RelationBreakdown-relaxed_y_true) (<code>list\[int\]</code>) –
- [**y_pred**](#agrag-eval-extraction-RelationBreakdown-y_pred) (<code>list\[int\]</code>) –
- [**y_true**](#agrag-eval-extraction-RelationBreakdown-y_true) (<code>list\[int\]</code>) –

## `kind` \{#agrag-eval-extraction-RelationBreakdown-kind}

```python
kind: Literal['entity', 'relation']
```

## `relaxed_y_pred` \{#agrag-eval-extraction-RelationBreakdown-relaxed_y_pred}

```python
relaxed_y_pred: list[int]
```

## `relaxed_y_true` \{#agrag-eval-extraction-RelationBreakdown-relaxed_y_true}

```python
relaxed_y_true: list[int]
```

## `y_pred` \{#agrag-eval-extraction-RelationBreakdown-y_pred}

```python
y_pred: list[int]
```

## `y_true` \{#agrag-eval-extraction-RelationBreakdown-y_true}

```python
y_true: list[int]
```
