---
title: agrag.ingestion.resolve.batch_validation.validate_batch_verdicts
sidebar_label: validate_batch_verdicts
---

# `agrag.ingestion.resolve.batch_validation.validate_batch_verdicts` \{#agrag-ingestion-resolve-batch_validation-validate_batch_verdicts}

```python
validate_batch_verdicts(pair_ids:Iterable[str], results:object) -> dict[str, ComparisonResult]
```

Return verdicts keyed by requested candidate pair identifiers.

Unknown, duplicate, missing, and malformed results leave a pair
`UNCERTAIN`. An answer the model never gave is not a rejection, and a valid
response is never assigned to a different pair.
