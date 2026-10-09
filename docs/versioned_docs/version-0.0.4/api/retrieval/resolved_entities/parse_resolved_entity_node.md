---
title: agrag.retrieval.resolved_entities.parse_resolved_entity_node
sidebar_label: parse_resolved_entity_node
---

# `agrag.retrieval.resolved_entities.parse_resolved_entity_node` \{#agrag-retrieval-resolved_entities-parse_resolved_entity_node}

```python
parse_resolved_entity_node(node:object) -> ResolvedEntity | None
```

Parse a graph-store node into a resolved entity when its shape is valid.

Accepts both the `{"properties": {...}}` mock shape used in tests and a
real Neo4j driver `Node`, which exposes its properties through
`dict(node)` rather than as a plain dict. Flat properties outside
`ResolvedEntity`'s own fields (for example `description`) are routed
into `ResolvedEntity.properties` instead of being dropped by pydantic.
