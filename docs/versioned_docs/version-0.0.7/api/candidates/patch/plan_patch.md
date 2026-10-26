---
title: agrag.candidates.patch.plan_patch
sidebar_label: plan_patch
---

# `agrag.candidates.patch.plan_patch` \{#agrag-candidates-patch-plan_patch}

```python
plan_patch(records:Sequence[CandidateRecord], *, schema:GraphSchema, labels_by_entity:Mapping[str, Sequence[str]], base:PatchBase, created_at:datetime) -> SchemaPatch
```

Plan sorted schema additions and evidence from candidate records.

Records with unresolved endpoints are excluded. Entity, relation, and
property changes already covered by the schema are omitted. A stable patch
identifier is derived from the base fingerprint and included record ids.

**Parameters:**

- **records** (<code>Sequence\[[CandidateRecord](../../common/data_models/candidate/CandidateRecord.md)\]</code>) – Candidate records considered for inclusion.
- **schema** (<code>[GraphSchema](../../common/data_models/graph_schema/GraphSchema.md)</code>) – Current schema used to identify existing definitions.
- **labels_by_entity** (<code>Mapping\[str, Sequence\[str\]\]</code>) – Graph labels keyed by entity id.
- **base** (<code>[PatchBase](../../common/data_models/candidate_review/PatchBase.md)</code>) – Name, version, and fingerprint of the base schema.
- **created_at** (<code>datetime</code>) – Timestamp recorded in the resulting patch.

**Returns:**

- <code>[SchemaPatch](../../common/data_models/candidate_review/SchemaPatch.md)</code> – Patch with sorted additions, evidence totals, and included candidate ids.
