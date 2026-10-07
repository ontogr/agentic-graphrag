---
title: agrag.ingestion.resolve.CandidateSource
sidebar_label: CandidateSource
---

# `agrag.ingestion.resolve.CandidateSource` \{#agrag-ingestion-resolve-CandidateSource}

Bases: <code>ABC</code>

Narrows which in-batch entity pairs resolution compares.

**Functions:**

- [**candidates_for**](#agrag-ingestion-resolve-CandidateSource-candidates_for) – Return indices worth comparing against `entities[index]`.

## `candidates_for` \{#agrag-ingestion-resolve-CandidateSource-candidates_for}

```python
candidates_for(index:int, entities:list[ExtractedEntity]) -> list[int]
```

Return indices worth comparing against `entities[index]`.
