---
title: agrag.common.data_models.evidence.CitationResult
sidebar_label: CitationResult
---

# `agrag.common.data_models.evidence.CitationResult` \{#agrag-common-data_models-evidence-CitationResult}

Bases: <code>BaseModel</code>

The verdicts of one citation check call.

**Attributes:**

- [**checks**](#agrag-common-data_models-evidence-CitationResult-checks) (<code>list\[[CitationCheck](CitationCheck.md)\]</code>) – One verdict for each cited id, in the order given.
- [**truncated**](#agrag-common-data_models-evidence-CitationResult-truncated) (<code>bool</code>) – True when trailing checks were dropped to stay within a
  serving layer's response-size limit.

## `checks` \{#agrag-common-data_models-evidence-CitationResult-checks}

```python
checks: list[CitationCheck] = Field(default_factory=list)
```

## `truncated` \{#agrag-common-data_models-evidence-CitationResult-truncated}

```python
truncated: bool = False
```
