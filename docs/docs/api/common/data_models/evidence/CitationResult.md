---
title: agrag.common.data_models.evidence.CitationResult
sidebar_label: CitationResult
---

# `agrag.common.data_models.evidence.CitationResult` \{#agrag-common-data_models-evidence-CitationResult}

Bases: <code>BaseModel</code>

The verdicts of one citation check call.

**Attributes:**

- [**checks**](#agrag-common-data_models-evidence-CitationResult-checks) (<code>list\[[CitationCheck](CitationCheck.md)\]</code>) – One verdict for each cited id, in the order given.

## `checks` \{#agrag-common-data_models-evidence-CitationResult-checks}

```python
checks: list[CitationCheck] = Field(default_factory=list)
```
