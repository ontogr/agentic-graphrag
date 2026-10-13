---
title: agrag.candidates.review.move_candidates
sidebar_label: move_candidates
---

# `agrag.candidates.review.move_candidates` \{#agrag-candidates-review-move_candidates}

```python
move_candidates(graph_store:GraphStore, rows:list[dict[str, str | None]], *, to_state:CandidateState, now:datetime | None = None) -> ReviewOutcome
```

Move candidate groups whose current states allow `to_state`.

Groups that are missing or cannot make the transition remain unchanged
and appear in `skipped`. Successful writes update the candidate state
and decision time.

**Parameters:**

- **graph_store** (<code>[GraphStore](../../graphdb/base/GraphStore.md)</code>) – Store containing the candidate groups.
- **rows** (<code>list\[dict\[str, str | None\]\]</code>) – Group keys and optional endpoint ids used for approval.
- **to_state** (<code>CandidateState</code>) – State to enter.
- **now** (<code>datetime | None</code>) – Decision time, or the current UTC time when omitted.

**Returns:**

- <code>[ReviewOutcome](../../common/data_models/candidate_review/ReviewOutcome.md)</code> – Keys changed and keys skipped with their reasons.
