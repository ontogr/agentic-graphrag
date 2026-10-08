---
title: agrag.ingestion.merge
sidebar_label: merge
---

# `agrag.ingestion.merge` \{#agrag-ingestion-merge}

Merge mechanics: how a resolved group of mentions and entities combine.

This module is storage-agnostic. It decides what a merge must look like,
but it never touches GraphStore itself. Applying a computed MergePlan is a
separate step.

**Classes:**

- [**ConflictRecord**](ConflictRecord.md) – One property that had more than one candidate value.
- [**MergePlan**](MergePlan.md) – Computed result of merging zero or more entities and mentions.
- [**PropertyRules**](PropertyRules.md) – Per-property conflict resolution, with a default for unlisted properties.
- [**PropertyStrategy**](PropertyStrategy.md) – Fallback rule for a property with no entry in PropertyRules.

**Functions:**

- [**apply_merge**](apply_merge.md) – Write a computed MergePlan to storage.
- [**compute_merge**](compute_merge.md) – Compute how existing_entities and mentions combine into one Entity.
- [**mentioned_in_id**](mentioned_in_id.md) – Return the deterministic id for a new Chunk MENTIONED_IN Entity edge.
- [**merge_properties**](merge_properties.md) – Return field-resolved properties and records of every real conflict.
- [**next_chunk_id**](next_chunk_id.md) – Return the deterministic id for a Chunk -[:NEXT_CHUNK]-> Chunk edge.
- [**part_of_id**](part_of_id.md) – Return the id for one versioned Document -[:PART_OF]-> node edge.
- [**relation_id**](relation_id.md) – Return the deterministic id for a domain relationship triple.
- [**resolve_description**](resolve_description.md) – Resolve a description field, trying LLM summarization.
- [**select_canonical**](select_canonical.md) – Return the canonical entity and the rest, from two or more entities.

**Attributes:**

- [**PropertyRule**](PropertyRule.md) – Per-property conflict resolver.
