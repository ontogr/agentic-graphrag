---
title: agrag.ingestion.materialize.deactivate_match_and_rematerialize
sidebar_label: deactivate_match_and_rematerialize
---

# `agrag.ingestion.materialize.deactivate_match_and_rematerialize` \{#agrag-ingestion-materialize-deactivate_match_and_rematerialize}

```python
deactivate_match_and_rematerialize(match_id:UUID, *, graph_store:GraphStore, schema:GraphSchema, tracer:Tracer | None = None) -> DeactivationResult
```

Deactivate a match and return its replacements and deleted derived IDs.
