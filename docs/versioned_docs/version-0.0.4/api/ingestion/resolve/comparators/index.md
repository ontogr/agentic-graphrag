---
title: agrag.ingestion.resolve.comparators
sidebar_label: comparators
---

# `agrag.ingestion.resolve.comparators` \{#agrag-ingestion-resolve-comparators}

Comparison strategies used by entity resolution.

**Classes:**

- [**Comparator**](Comparator.md) – One matching strategy a Resolver runs against a candidate pair.
- [**ComparisonResult**](ComparisonResult.md) – The verdict and evidence produced by one comparator.
- [**ComparisonVerdict**](ComparisonVerdict.md) – A Comparator's verdict on one entity pair.
- [**ExactMatch**](ExactMatch.md) – Matches when normalized text is identical. Never returns NO_MATCH.
- [**FuzzyMatch**](FuzzyMatch.md) – Fast-path accepter for near-identical names. Never returns NO_MATCH.
- [**LLMVerify**](LLMVerify.md) – Asks an LLM to verify an ambiguous pair. Last resort; never UNCERTAIN.
