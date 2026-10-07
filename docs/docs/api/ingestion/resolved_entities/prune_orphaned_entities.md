---
title: agrag.ingestion.resolved_entities.prune_orphaned_entities
sidebar_label: prune_orphaned_entities
---

# `agrag.ingestion.resolved_entities.prune_orphaned_entities` \{#agrag-ingestion-resolved_entities-prune_orphaned_entities}

```python
prune_orphaned_entities(candidate_entity_ids:list[UUID], *, graph_store:GraphStore, schema:GraphSchema, tracer:Tracer | None = None) -> PruningResult
```

Delete candidates with no open-chunk evidence and rebuild clusters.

A candidate mentioned by any chunk with an open PART_OF edge keeps its
node. Any other candidate loses its node with its incident MENTIONED_IN
and RESOLVED_AS edges; each affected cluster is then recomputed over
its remaining members, or deleted when fewer than two remain and the
survivor returns to plain status. Merge aliases owned by removed
entities are deleted too, so re-ingesting a pruned name starts clean
instead of colliding with an alias pointing at a missing node.

Only the supplied candidates are ever deleted. Evidence is checked per
candidate id, never with a graph-wide scan.
