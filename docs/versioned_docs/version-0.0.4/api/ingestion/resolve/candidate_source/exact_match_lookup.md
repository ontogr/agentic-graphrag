---
title: agrag.ingestion.resolve.candidate_source.exact_match_lookup
sidebar_label: exact_match_lookup
---

# `agrag.ingestion.resolve.candidate_source.exact_match_lookup` \{#agrag-ingestion-resolve-candidate_source-exact_match_lookup}

```python
exact_match_lookup(mentions:list[ExtractedEntity], *, graph_store:GraphStore) -> dict[int, Entity]
```

Return persisted exact matches, including resolved tombstone aliases.
