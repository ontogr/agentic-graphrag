---
title: agrag.candidates.review.approve_candidates
sidebar_label: approve_candidates
---

# `agrag.candidates.review.approve_candidates` \{#agrag-candidates-review-approve_candidates}

```python
approve_candidates(graph_store:GraphStore, schema:GraphSchema, *, ids:Sequence[UUID] | None = None, query:CandidateQuery | None = None, output:Path | None = None, overwrite:bool = False, now:datetime | None = None) -> ApprovalResult
```

Approve resolvable candidates and plan a deterministic schema patch.

Pass exactly one of `ids` or `query`. Only pending candidates with
resolvable endpoints are approved. If any candidate changes state, a patch
is built from the approved groups; `output` also writes it as JSON.

**Parameters:**

- **graph_store** (<code>[GraphStore](../../graphdb/base/GraphStore.md)</code>) – Store containing candidates and endpoint entities.
- **schema** (<code>[GraphSchema](../../common/data_models/graph_schema/GraphSchema.md)</code>) – Schema used to resolve endpoints and plan additions.
- **ids** (<code>Sequence\[UUID\] | None</code>) – Candidate ids to approve.
- **query** (<code>[CandidateQuery](../../common/data_models/candidate_review/CandidateQuery.md) | None</code>) – Filters used to select candidate ids.
- **output** (<code>Path | None</code>) – Optional path for the patch JSON file.
- **overwrite** (<code>bool</code>) – Whether to replace an existing output file.
- **now** (<code>datetime | None</code>) – Decision and patch creation time, or current UTC time.

**Returns:**

- <code>[ApprovalResult](../../common/data_models/candidate_review/ApprovalResult.md)</code> – Approval results and a patch when at least one group changes state.
- <code>[ApprovalResult](../../common/data_models/candidate_review/ApprovalResult.md)</code> – The output path is set only when the file was written.

**Raises:**

- <code>ValueError</code> – If both or neither of `ids` and `query` are supplied.
- <code>FileExistsError</code> – If `output` exists and `overwrite` is false.
