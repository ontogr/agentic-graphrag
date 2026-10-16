---
title: agrag.ingestion.resolve.resolver.FuzzyMatch
sidebar_label: FuzzyMatch
---

# `agrag.ingestion.resolve.resolver.FuzzyMatch` \{#agrag-ingestion-resolve-resolver-FuzzyMatch}

```python
FuzzyMatch(*, match_above:float = 0.97) -> None
```

Bases: <code>[Comparator](Comparator.md)</code>

Fast-path accepter for near-identical names. Never returns NO_MATCH.

Rejection belongs to later tiers, which see embedding and LLM evidence
this comparator lacks.

**Attributes:**

- [**match_above**](#agrag-ingestion-resolve-resolver-FuzzyMatch-match_above) – A similarity score at or above this is a match.

**Functions:**

- [**compare**](#agrag-ingestion-resolve-resolver-FuzzyMatch-compare) – Return a verdict from token-sort-ratio similarity.
- [**compare_with_evidence**](#agrag-ingestion-resolve-resolver-FuzzyMatch-compare_with_evidence) – Compare two entities and include their token-sort similarity.

## `compare` \{#agrag-ingestion-resolve-resolver-FuzzyMatch-compare}

```python
compare(a:ExtractedEntity, b:ExtractedEntity) -> ComparisonVerdict
```

Return a verdict from token-sort-ratio similarity.

## `compare_with_evidence` \{#agrag-ingestion-resolve-resolver-FuzzyMatch-compare_with_evidence}

```python
compare_with_evidence(a:ExtractedEntity, b:ExtractedEntity) -> ComparisonResult
```

Compare two entities and include their token-sort similarity.

## `match_above` \{#agrag-ingestion-resolve-resolver-FuzzyMatch-match_above}

```python
match_above = match_above
```
