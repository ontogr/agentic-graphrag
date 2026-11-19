---
title: agrag.candidates.ReviewOutcome
sidebar_label: ReviewOutcome
---

# `agrag.candidates.ReviewOutcome` \{#agrag-candidates-ReviewOutcome}

Bases: <code>BaseModel</code>

Report candidate groups moved and groups that could not be moved.

**Attributes:**

- [**changed**](#agrag-candidates-ReviewOutcome-changed) (<code>list\[str\]</code>) – Keys whose groups changed state.
- [**skipped**](#agrag-candidates-ReviewOutcome-skipped) (<code>dict\[str, str\]</code>) – Keys not changed, mapped to the reason they were skipped.

## `changed` \{#agrag-candidates-ReviewOutcome-changed}

```python
changed: list[str] = Field(default_factory=list)
```

## `skipped` \{#agrag-candidates-ReviewOutcome-skipped}

```python
skipped: dict[str, str] = Field(default_factory=dict)
```
