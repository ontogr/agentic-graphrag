---
title: agrag.candidates.review.prune_candidates
sidebar_label: prune_candidates
---

# `agrag.candidates.review.prune_candidates` \{#agrag-candidates-review-prune_candidates}

```python
prune_candidates(graph_store:GraphStore, *, rejected:bool = False, pending_older_than_days:int | None = None, pending_below_count:int | None = None, apply:bool = False, now:datetime | None = None) -> PruneReport
```

Count or delete groups matching the selected prune criteria.

Matching groups are only deleted when `apply` is true and at least
one group matches. The report distinguishes a dry run from a deletion.

**Parameters:**

- **graph_store** (<code>[GraphStore](../../graphdb/base/GraphStore.md)</code>) – Store containing candidate groups.
- **rejected** (<code>bool</code>) – Include rejected groups.
- **pending_older_than_days** (<code>int | None</code>) – Include pending groups older than this many days.
- **pending_below_count** (<code>int | None</code>) – Include pending groups below this sighting count.
- **apply** (<code>bool</code>) – Whether to delete matching groups.
- **now** (<code>datetime | None</code>) – Reference time, or the current UTC time when omitted.

**Returns:**

- <code>[PruneReport](../../common/data_models/candidate_review/PruneReport.md)</code> – Counts of matched and deleted groups and whether deletion ran.

**Raises:**

- <code>ValueError</code> – If no criterion is set or a numeric threshold is below one.
