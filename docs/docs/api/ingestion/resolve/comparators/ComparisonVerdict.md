---
title: agrag.ingestion.resolve.comparators.ComparisonVerdict
sidebar_label: ComparisonVerdict
---

# `agrag.ingestion.resolve.comparators.ComparisonVerdict` \{#agrag-ingestion-resolve-comparators-ComparisonVerdict}

Bases: <code>StrEnum</code>

A Comparator's verdict on one entity pair.

**Attributes:**

- [**MATCH**](#agrag-ingestion-resolve-comparators-ComparisonVerdict-MATCH) – The comparator is confident these are the same entity.
- [**NO_MATCH**](#agrag-ingestion-resolve-comparators-ComparisonVerdict-NO_MATCH) – The comparator is confident these are different entities.
- [**UNCERTAIN**](#agrag-ingestion-resolve-comparators-ComparisonVerdict-UNCERTAIN) – This comparator can't decide; the next one gets a turn.

## `MATCH` \{#agrag-ingestion-resolve-comparators-ComparisonVerdict-MATCH}

```python
MATCH = 'match'
```

## `NO_MATCH` \{#agrag-ingestion-resolve-comparators-ComparisonVerdict-NO_MATCH}

```python
NO_MATCH = 'no_match'
```

## `UNCERTAIN` \{#agrag-ingestion-resolve-comparators-ComparisonVerdict-UNCERTAIN}

```python
UNCERTAIN = 'uncertain'
```
