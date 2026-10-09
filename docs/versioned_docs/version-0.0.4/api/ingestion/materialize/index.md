---
title: agrag.ingestion.materialize
sidebar_label: materialize
---

# `agrag.ingestion.materialize` \{#agrag-ingestion-materialize}

Non-destructive match persistence and resolved-entity computation.

**Classes:**

- [**DeactivationResult**](DeactivationResult.md) – Materializations created after a match correction and stale ids removed.
- [**MatchDecision**](MatchDecision.md) – A confirmed non-exact entity match ready to persist.
- [**MaterializationResult**](MaterializationResult.md) – The derived entity created and prior derived ids it replaced.
- [**PruningResult**](PruningResult.md) – Ids removed and clusters rebuilt by deletion-triggered pruning.

**Functions:**

- [**compute_resolved_entity**](compute_resolved_entity.md) – Compute a resolved entity from its current member data only.
- [**deactivate_match_and_rematerialize**](deactivate_match_and_rematerialize.md) – Deactivate a match and return its replacements and deleted derived IDs.
- [**decisions_by_component**](decisions_by_component.md) – Map resolution evidence to raw ids and group it by connected component.
- [**match_decision_components**](match_decision_components.md) – Group persisted match decisions by their connected raw component.
- [**matches_id**](matches_id.md) – Return the order-independent deterministic id for an entity match.
- [**prune_orphaned_entities**](prune_orphaned_entities.md) – Delete candidates with no open-chunk evidence and rebuild clusters.
- [**write_matches_and_materialize**](write_matches_and_materialize.md) – Persist matches and materialize their supplied connected component.

**Attributes:**

- [**MatchComponent**](MatchComponent.md) – One connected component: its match decisions and its raw member entities.
