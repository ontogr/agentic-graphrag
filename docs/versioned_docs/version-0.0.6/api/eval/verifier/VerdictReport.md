---
title: agrag.eval.verifier.VerdictReport
sidebar_label: VerdictReport
---

# `agrag.eval.verifier.VerdictReport` \{#agrag-eval-verifier-VerdictReport}

Bases: <code>BaseModel</code>

Scores of predicted verdicts against gold verdicts.

**Attributes:**

- [**labels**](#agrag-eval-verifier-VerdictReport-labels) (<code>list\[str\]</code>) – The class order of `confusion_matrix`.
- [**per_class**](#agrag-eval-verifier-VerdictReport-per_class) (<code>dict\[str, [ClassScores](ClassScores.md)\]</code>) – Scores for each class.
- [**macro_f1**](#agrag-eval-verifier-VerdictReport-macro_f1) (<code>float</code>) – The mean F1 over the three classes.
- [**confusion_matrix**](#agrag-eval-verifier-VerdictReport-confusion_matrix) (<code>list\[list\[int\]\]</code>) – Counts with gold classes as rows and predicted classes
  as columns. A prediction of `ERROR` is in no column.
- [**errors**](#agrag-eval-verifier-VerdictReport-errors) (<code>int</code>) – The number of `ERROR` predictions. Each one is a miss for
  the gold class of its item.

## `confusion_matrix` \{#agrag-eval-verifier-VerdictReport-confusion_matrix}

```python
confusion_matrix: list[list[int]]
```

## `errors` \{#agrag-eval-verifier-VerdictReport-errors}

```python
errors: int
```

## `labels` \{#agrag-eval-verifier-VerdictReport-labels}

```python
labels: list[str]
```

## `macro_f1` \{#agrag-eval-verifier-VerdictReport-macro_f1}

```python
macro_f1: float
```

## `per_class` \{#agrag-eval-verifier-VerdictReport-per_class}

```python
per_class: dict[str, ClassScores]
```
