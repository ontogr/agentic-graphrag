---
title: agrag.ingestion.resolve.resolver.ExactMatch
sidebar_label: ExactMatch
---

# `agrag.ingestion.resolve.resolver.ExactMatch` \{#agrag-ingestion-resolve-resolver-ExactMatch}

Bases: <code>[Comparator](Comparator.md)</code>

Matches when normalized text is identical. Never returns NO_MATCH.

**Functions:**

- [**compare**](#agrag-ingestion-resolve-resolver-ExactMatch-compare) – Return MATCH on identical normalized text, else UNCERTAIN.
- [**compare_with_evidence**](#agrag-ingestion-resolve-resolver-ExactMatch-compare_with_evidence) – Compare two entities and retain any available decision evidence.

## `compare` \{#agrag-ingestion-resolve-resolver-ExactMatch-compare}

```python
compare(a:ExtractedEntity, b:ExtractedEntity) -> ComparisonVerdict
```

Return MATCH on identical normalized text, else UNCERTAIN.

## `compare_with_evidence` \{#agrag-ingestion-resolve-resolver-ExactMatch-compare_with_evidence}

```python
compare_with_evidence(a:ExtractedEntity, b:ExtractedEntity) -> ComparisonResult
```

Compare two entities and retain any available decision evidence.
