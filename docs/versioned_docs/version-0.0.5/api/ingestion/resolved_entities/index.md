---
title: agrag.ingestion.resolved_entities
sidebar_label: resolved_entities
---

# `agrag.ingestion.resolved_entities` \{#agrag-ingestion-resolved_entities}

Non-destructive match persistence and resolved-entity computation.

**Classes:**

- [**DeactivationResult**](DeactivationResult.md) – Resolved entities created after a match correction and stale ids removed.
- [**MatchDecision**](MatchDecision.md) – A confirmed non-exact entity match ready to persist.
- [**PruningResult**](PruningResult.md) – Ids removed and clusters rebuilt by deletion-triggered pruning.
- [**RebuildResult**](RebuildResult.md) – The derived entity created and prior derived ids it replaced.

**Functions:**

- [**compute_resolved_entity**](compute_resolved_entity.md) – Compute a resolved entity from its current member data only.
- [**deactivate_match_and_rebuild**](deactivate_match_and_rebuild.md) – Deactivate a match and return its replacements and deleted derived IDs.
- [**decisions_by_component**](decisions_by_component.md) – Map resolution evidence to raw ids and group it by connected component.
- [**match_decision_components**](match_decision_components.md) – Group persisted match decisions by their connected raw component.
- [**matches_id**](matches_id.md) – Return the order-independent deterministic id for an entity match.
- [**prune_orphaned_entities**](prune_orphaned_entities.md) – Delete candidates with no open-chunk evidence and rebuild clusters.
- [**rebuild_resolved_entities**](rebuild_resolved_entities.md) – Rebuild the resolved entity of each committed component from its seeds.
- [**write_matches_and_rebuild**](write_matches_and_rebuild.md) – Persist matches and rebuild their supplied connected component.

**Attributes:**

- [**MatchComponent**](MatchComponent.md) – One connected component: its match decisions and its raw member entities.
