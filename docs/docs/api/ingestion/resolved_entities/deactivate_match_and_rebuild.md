---
title: agrag.ingestion.resolved_entities.deactivate_match_and_rebuild
sidebar_label: deactivate_match_and_rebuild
---

# `agrag.ingestion.resolved_entities.deactivate_match_and_rebuild` \{#agrag-ingestion-resolved_entities-deactivate_match_and_rebuild}

```python
deactivate_match_and_rebuild(match_id:UUID, *, graph_store:GraphStore, schema:GraphSchema, tracer:Tracer | None = None) -> DeactivationResult
```

Deactivate a match and return its replacements and deleted derived IDs.
