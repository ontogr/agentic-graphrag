---
title: agrag.ingestion.resolve.batch_validation.validate_batch_verdicts
sidebar_label: validate_batch_verdicts
---

# `agrag.ingestion.resolve.batch_validation.validate_batch_verdicts` \{#agrag-ingestion-resolve-batch_validation-validate_batch_verdicts}

```python
validate_batch_verdicts(pair_ids:Iterable[str], results:Iterable[object]) -> dict[str, ComparisonResult]
```

Return fail-safe verdicts keyed by requested candidate pair identifiers.

Unknown, duplicate, missing, and malformed results resolve to `NO_MATCH`.
This avoids assigning a valid LLM response to a different candidate pair.
