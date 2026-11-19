---
title: agrag.candidates.review.list_candidates
sidebar_label: list_candidates
---

# `agrag.candidates.review.list_candidates` \{#agrag-candidates-review-list_candidates}

```python
list_candidates(graph_store:GraphStore, query:CandidateQuery | None = None, *, limit:int = 100, skip:int = 0, schema:GraphSchema | None = None, include_covered:bool = False) -> list[CandidateGroup]
```

List candidate groups, ordered and paged by aggregate sightings.

When a schema is supplied, covered pending candidates are hidden unless
`include_covered` is true.

**Parameters:**

- **graph_store** (<code>[GraphStore](../../graphdb/base/GraphStore.md)</code>) – Store used to read candidate groups.
- **query** (<code>[CandidateQuery](../../common/data_models/candidate_review/CandidateQuery.md) | None</code>) – Optional filters for kind, label, state, and sighting count.
- **limit** (<code>int</code>) – Maximum number of groups to return.
- **skip** (<code>int</code>) – Number of groups to skip.
- **schema** (<code>[GraphSchema](../../common/data_models/graph_schema/GraphSchema.md) | None</code>) – Schema used to identify already-covered candidates.
- **include_covered** (<code>bool</code>) – Whether to retain candidates covered by the schema.

**Returns:**

- <code>list\[[CandidateGroup](../../common/data_models/candidate_review/CandidateGroup.md)\]</code> – Matching candidate groups.

**Raises:**

- <code>ValueError</code> – If `limit` or `skip` is negative.
