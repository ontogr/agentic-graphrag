---
title: agrag.common.data_models.candidate_review
sidebar_label: candidate_review
---

# `agrag.common.data_models.candidate_review` \{#agrag-common-data_models-candidate_review}

Models for candidate review and schema patches.

**Classes:**

- [**ApprovalResult**](ApprovalResult.md) – Report approvals and the patch built from them.
- [**CandidateGroup**](CandidateGroup.md) – A deduplicated group of candidate nodes in one review state.
- [**CandidateQuery**](CandidateQuery.md) – Filter candidate groups by kind, label, state, and total sightings.
- [**PatchBase**](PatchBase.md) – Identify the schema used to plan the patch.
- [**PatchProperty**](PatchProperty.md) – Describe a property to add to an entity type.
- [**PruneReport**](PruneReport.md) – Report groups matched and deleted by a prune operation.
- [**ReviewOutcome**](ReviewOutcome.md) – Report candidate groups moved and groups that could not be moved.
- [**SchemaPatch**](SchemaPatch.md) – A deterministic schema change set and its approved candidate ids.

**Functions:**

- [**states_that_reach**](states_that_reach.md) – List source states from which a candidate can enter `target`.

**Attributes:**

- [**ALLOWED_TRANSITIONS**](ALLOWED_TRANSITIONS.md) (<code>dict\[[CandidateState](../candidate/CandidateState.md), frozenset\[[CandidateState](../candidate/CandidateState.md)\]\]</code>) –
- [**PATCH_FORMAT**](PATCH_FORMAT.md) –
- [**PATCH_README**](PATCH_README.md) –
