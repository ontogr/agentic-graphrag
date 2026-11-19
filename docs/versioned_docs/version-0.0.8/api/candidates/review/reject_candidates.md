---
title: agrag.candidates.review.reject_candidates
sidebar_label: reject_candidates
---

# `agrag.candidates.review.reject_candidates` \{#agrag-candidates-review-reject_candidates}

```python
reject_candidates(graph_store:GraphStore, *, keys:Sequence[str] | None = None, query:CandidateQuery | None = None, now:datetime | None = None) -> ReviewOutcome
```

Reject selected candidate groups and retain them as suppression records.

Pass exactly one of `keys` or `query`. Query selection deduplicates
keys before attempting the pending-to-rejected transition.

**Parameters:**

- **graph_store** (<code>[GraphStore](../../graphdb/base/GraphStore.md)</code>) – Store containing candidate groups.
- **keys** (<code>Sequence\[str\] | None</code>) – Explicit group keys to reject.
- **query** (<code>[CandidateQuery](../../common/data_models/candidate_review/CandidateQuery.md) | None</code>) – Filters used to select groups to reject.
- **now** (<code>datetime | None</code>) – Decision time, or the current UTC time when omitted.

**Returns:**

- <code>[ReviewOutcome](../../common/data_models/candidate_review/ReviewOutcome.md)</code> – Keys rejected and keys skipped with their reasons.

**Raises:**

- <code>ValueError</code> – If both or neither of `keys` and `query` are supplied.
