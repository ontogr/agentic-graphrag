---
title: agrag.candidates
sidebar_position: 13
---


# `agrag.candidates` \{#agrag-candidates}

Review extraction candidates and prepare schema patches.

**Modules:**

- [**errors**](errors/index.md) – Errors raised by candidate review operations.
- [**patch**](patch/index.md) – Plan and serialize deterministic candidate schema patches.
- [**review**](review/index.md) – List and change the review state of candidate groups.
- [**search**](search/index.md) – Word search over pending and approved candidates.

**Classes:**

- [**ApprovalResult**](ApprovalResult.md) – Report approvals and the patch built from them.
- [**CandidateQuery**](CandidateQuery.md) – Filter candidate groups by kind, label, state, and total sightings.
- [**PatchNotAppliedError**](errors/PatchNotAppliedError.md) – The active schema does not contain every change in a patch.
- [**PruneReport**](PruneReport.md) – Report groups matched and deleted by a prune operation.
- [**ReviewOutcome**](ReviewOutcome.md) – Report candidate groups moved and groups that could not be moved.
- [**SchemaPatch**](SchemaPatch.md) – A deterministic schema change set and its approved candidate ids.

**Functions:**

- [**approve_candidates**](review/approve_candidates.md) – Approve resolvable candidates and plan a deterministic schema patch.
- [**candidate_patch**](patch/candidate_patch.md) – Build a patch from approved candidate records in the graph.
- [**list_candidates**](review/list_candidates.md) – List candidate groups, ordered and paged by aggregate sightings.
- [**prune_candidates**](review/prune_candidates.md) – Count or delete groups matching the selected prune criteria.
- [**read_patch**](patch/read_patch.md) – Read a JSON file and validate it as a schema patch.
- [**reject_candidates**](review/reject_candidates.md) – Reject selected candidate groups and retain them as suppression records.
- [**search_candidates**](search/search_candidates.md) – Find candidates whose label or text holds any word of the query.
- [**write_patch**](patch/write_patch.md) – Write the patch as indented JSON, refusing replacement by default.
