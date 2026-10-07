---
title: agrag.ingestion.resolve.comparators.Comparator
sidebar_label: Comparator
---

# `agrag.ingestion.resolve.comparators.Comparator` \{#agrag-ingestion-resolve-comparators-Comparator}

Bases: <code>ABC</code>

One matching strategy a Resolver runs against a candidate pair.

**Functions:**

- [**compare**](#agrag-ingestion-resolve-comparators-Comparator-compare) – Compare two entities.
- [**compare_with_evidence**](#agrag-ingestion-resolve-comparators-Comparator-compare_with_evidence) – Compare two entities and retain any available decision evidence.

## `compare` \{#agrag-ingestion-resolve-comparators-Comparator-compare}

```python
compare(a:ExtractedEntity, b:ExtractedEntity) -> ComparisonVerdict
```

Compare two entities.

**Parameters:**

- **a** (<code>[ExtractedEntity](../../../common/data_models/extraction/ExtractedEntity.md)</code>) – The first entity.
- **b** (<code>[ExtractedEntity](../../../common/data_models/extraction/ExtractedEntity.md)</code>) – The second entity.

**Returns:**

- <code>[ComparisonVerdict](ComparisonVerdict.md)</code> – This comparator's verdict. UNCERTAIN defers to the next comparator.

## `compare_with_evidence` \{#agrag-ingestion-resolve-comparators-Comparator-compare_with_evidence}

```python
compare_with_evidence(a:ExtractedEntity, b:ExtractedEntity) -> ComparisonResult
```

Compare two entities and retain any available decision evidence.
