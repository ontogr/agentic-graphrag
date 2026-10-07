---
title: agrag.ingestion.resolve.candidate_source.PersistedCandidateSource
sidebar_label: PersistedCandidateSource
---

# `agrag.ingestion.resolve.candidate_source.PersistedCandidateSource` \{#agrag-ingestion-resolve-candidate_source-PersistedCandidateSource}

```python
PersistedCandidateSource(candidates_by_index:dict[int, list[int]]) -> None
```

Bases: <code>[CandidateSource](CandidateSource.md)</code>

Supplies only candidate pairs between new mentions and raw graph entities.

**Functions:**

- [**candidates_for**](#agrag-ingestion-resolve-candidate_source-PersistedCandidateSource-candidates_for) – Return persisted candidates for a newly extracted mention.

**Attributes:**

- [**candidates_by_index**](#agrag-ingestion-resolve-candidate_source-PersistedCandidateSource-candidates_by_index) –

## `candidates_by_index` \{#agrag-ingestion-resolve-candidate_source-PersistedCandidateSource-candidates_by_index}

```python
candidates_by_index = candidates_by_index
```

## `candidates_for` \{#agrag-ingestion-resolve-candidate_source-PersistedCandidateSource-candidates_for}

```python
candidates_for(index:int, entities:list[ExtractedEntity]) -> list[int]
```

Return persisted candidates for a newly extracted mention.
