---
title: agrag.common.data_models.decision.ReviewState
sidebar_label: ReviewState
---

# `agrag.common.data_models.decision.ReviewState` \{#agrag-common-data_models-decision-ReviewState}

Bases: <code>StrEnum</code>

Whether a decision's supports still hold.

`needs_review` means a source changed and someone should look again. It
does not mean the decision is false. `unknown` means the review state
could not be established, so the decision is treated as needing review.

**Attributes:**

- [**CLEAR**](#agrag-common-data_models-decision-ReviewState-CLEAR) –
- [**NEEDS_REVIEW**](#agrag-common-data_models-decision-ReviewState-NEEDS_REVIEW) –
- [**UNKNOWN**](#agrag-common-data_models-decision-ReviewState-UNKNOWN) –

## `CLEAR` \{#agrag-common-data_models-decision-ReviewState-CLEAR}

```python
CLEAR = 'clear'
```

## `NEEDS_REVIEW` \{#agrag-common-data_models-decision-ReviewState-NEEDS_REVIEW}

```python
NEEDS_REVIEW = 'needs_review'
```

## `UNKNOWN` \{#agrag-common-data_models-decision-ReviewState-UNKNOWN}

```python
UNKNOWN = 'unknown'
```
